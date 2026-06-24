"""Custom fast saturable absorber component for mode-locking.

pyLaserPulse does not ship a saturable absorber, so this provides a simple
fast-SA model that plugs into the optical_assemblies machinery. The
instantaneous power-dependent transmission is:

    T(t) = 1 - q0 / (1 + P(t) / P_sat)

where q0 is the modulation depth (saturable loss) and P_sat is the
saturation power. High-intensity peaks see higher transmission than the
low-intensity wings/noise, which favours pulse formation from noise.
"""

import numpy as np

import pyLaserPulse.base_components as bc


class FastSaturableAbsorber(bc.component):
    """Fast saturable absorber modelled as an instantaneous power filter."""

    def __init__(self, grid, mod_depth=0.4, sat_power=300.0,
                 non_sat_loss=0.0, lambda_c=None, verbose=False):
        """
        Parameters
        ----------
        grid : pyLaserPulse.grid.grid object
        mod_depth : float
            Modulation depth q0 (0..1). Fraction of low-power light absorbed.
        sat_power : float
            Saturation power in W.
        non_sat_loss : float
            Non-saturable insertion loss (0..1).
        lambda_c : float or None
            Central wavelength. Defaults to grid.lambda_c.
        verbose : bool
        """
        if lambda_c is None:
            lambda_c = grid.lambda_c

        # trans_bw set very wide so the linear transmission window is flat
        # across the whole grid; the SA action is applied in propagate().
        super().__init__(
            non_sat_loss, 1.0, lambda_c, 1.0, 0.0, 0.0, grid, 1e-3,
            order=2, output_coupler=False)

        self.mod_depth = float(np.clip(mod_depth, 0.0, 1.0))
        self.sat_power = max(float(sat_power), 1e-12)
        self.verbose = verbose

    @bc.component.propagator
    def propagate(self, pulse):
        power = np.sum(np.abs(pulse.field) ** 2, axis=0)
        transmission = 1.0 - self.mod_depth / (1.0 + power / self.sat_power)
        transmission = np.clip(transmission, 0.0, 1.0)
        pulse.field = pulse.field * np.sqrt(transmission)
        return pulse
