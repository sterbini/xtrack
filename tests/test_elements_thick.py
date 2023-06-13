# copyright ############################### #
# This file is part of the Xtrack Package.  #
# Copyright (c) CERN, 2023.                 #
# ######################################### #
import numpy as np
import pytest
import xobjects as xo
import xpart as xp
from cpymad.madx import Madx
from xobjects.test_helpers import for_all_test_contexts

import xtrack as xt
from xtrack.mad_loader import MadLoader


@pytest.mark.parametrize(
    'k0, k1, length',
    [
        (-0.1, 0, 0.9),
        (0, 0, 0.9),
        (-0.1, 0.12, 0.9),
        (0, 0.12, 0.8),
        (0.15, -0.23, 0.9),
        (0, 0.13, 1.7),
    ]
)
@for_all_test_contexts
def test_combined_function_dipole_against_madx(test_context, k0, k1, length):
    """
    Test the combined function dipole against madx. We import bends from madx
    using use_true_thick_bend=False, and the true bend is not in madx.
    """
    rng = np.random.default_rng(123)
    num_part = 100

    p0 = xp.Particles(
        p0c=xp.PROTON_MASS_EV,
        x=rng.uniform(-1e-3, 1e-3, num_part),
        px=rng.uniform(-1e-5, 1e-5, num_part),
        y=rng.uniform(-2e-3, 2e-3, num_part),
        py=rng.uniform(-3e-5, 3e-5, num_part),
        zeta=rng.uniform(-1e-2, 1e-2, num_part),
        delta=rng.uniform(-1e-4, 1e-4, num_part),
        _context=test_context,
    )
    mad = Madx()
    mad.input(f"""
    ss: sequence, l={length};
        b: sbend, at={length / 2}, angle={k0 * length}, k1={k1}, l={length};
    endsequence;
    beam;
    use, sequence=ss;
    """)

    ml = MadLoader(mad.sequence.ss, allow_thick=True, use_true_thick_bends=False)
    line_thick = ml.make_line()
    line_thick.build_tracker(_context=test_context)

    for ii in range(num_part):
        mad.input(f"""
        beam, particle=proton, pc={p0.p0c[ii] / 1e9}, sequence=ss, radiate=FALSE;

        track, onepass, onetable;
        start, x={p0.x[ii]}, px={p0.px[ii]}, y={p0.y[ii]}, py={p0.py[ii]}, \
            t={p0.zeta[ii]/p0.beta0[ii]}, pt={p0.ptau[ii]};
        run, turns=1;
        endtrack;
        """)

        mad_results = mad.table.mytracksumm[-1]

        p = p0.copy(_context=xo.ContextCpu())
        line_thick.track(p, _force_no_end_turn_actions=True)

        xt_tau = p.zeta/p.beta0
        assert np.allclose(p.x[ii], mad_results.x, atol=1e-13, rtol=0)
        assert np.allclose(p.px[ii], mad_results.px, atol=1e-13, rtol=0)
        assert np.allclose(p.y[ii], mad_results.y, atol=1e-13, rtol=0)
        assert np.allclose(p.py[ii], mad_results.py, atol=1e-13, rtol=0)
        assert np.allclose(xt_tau[ii], mad_results.t, atol=2e-8, rtol=0)
        assert np.allclose(p.ptau[ii], mad_results.pt, atol=1e-13, rtol=0)


def test_thick_bend_survey():
    circumference = 10
    rho = circumference / (2 * np.math.pi)
    h = 1 / rho
    k = 1 / rho

    p0 = xp.Particles(p0c=7e12, mass0=xp.PROTON_MASS_EV, x=0.7, px=-0.4, delta=0.0)

    el = xt.TrueBend(k0=k, h=h, length=circumference, num_multipole_kicks=0)
    line = xt.Line(elements=[el])
    line.reset_s_at_end_turn = False
    line.build_tracker()

    s_array = np.linspace(0, circumference, 1000)

    X0_array = np.zeros_like(s_array)
    Z0_array = np.zeros_like(s_array)

    X_array = np.zeros_like(s_array)
    Z_array = np.zeros_like(s_array)

    for ii, s in enumerate(s_array):
        p = p0.copy()

        el.length = s
        el.knl = np.array([3e-4, 4e-4, 0, 0, 0]) * s / circumference
        line.track(p)

        theta = s / rho

        X0 = -rho * (1 - np.cos(theta))
        Z0 = rho * np.sin(theta)

        ex_X = np.cos(theta)
        ex_Z = np.sin(theta)

        X0_array[ii] = X0
        Z0_array[ii] = Z0

        X_array[ii] = X0 + p.x[0] * ex_X
        Z_array[ii] = Z0 + p.x[0] * ex_Z

    Xmid = (np.min(X_array) + np.max(X_array)) / 2
    Zmid = (np.min(Z_array) + np.max(Z_array)) / 2
    Xc = X_array - Xmid
    Zc = Z_array - Zmid
    rhos = np.sqrt(Xc ** 2 + Zc ** 2)
    errors = np.max(np.abs(rhos - 10 / (2 * np.math.pi)))
    assert errors < 2e-6


@pytest.mark.parametrize('element_type', [xt.TrueBend, xt.CombinedFunctionMagnet])
@pytest.mark.parametrize('h', [0.0, 0.1])
def test_thick_multipolar_component(element_type, h):
    bend_length = 1.0
    k0 = h
    knl = np.array([0.0, 0.01, -0.02, 0.03])
    ksl = np.array([0.0, -0.03, 0.02, -0.01])
    num_kicks = 2

    # Bend with a multipolar component
    bend_with_mult = element_type(
        k0=k0,
        h=h,
        length=bend_length,
        knl=knl,
        ksl=ksl,
        num_multipole_kicks=num_kicks,
    )

    # Separate bend and a corresponding multipole
    bend_no_mult = element_type(
        k0=k0,
        h=h,
        length=bend_length / (num_kicks + 1),
        num_multipole_kicks=0,
    )
    multipole = xt.Multipole(
        knl=knl / num_kicks,
        ksl=ksl / num_kicks,
    )

    # Two lines that should be equivalent
    line_no_slices = xt.Line(
        elements=[bend_with_mult],
        element_names=['bend_with_mult'],
    )
    line_with_slices = xt.Line(
        elements={'bend_no_mult': bend_no_mult, 'multipole': multipole},
        element_names=(['bend_no_mult', 'multipole'] * num_kicks) + ['bend_no_mult'],
    )

    # Track some particles
    p0 = xp.Particles(x=0.1, px=0.2, y=0.3, py=0.4, zeta=0.5, delta=0.6)

    p_no_slices = p0.copy()
    line_no_slices.build_tracker()
    line_no_slices.track(p_no_slices)

    p_with_slices = p0.copy()
    line_with_slices.build_tracker()
    line_with_slices.track(p_with_slices, turn_by_turn_monitor='ONE_TURN_EBE')

    print(f'with slices: {line_with_slices.record_last_track.x}')

    # Check that the results are the same
    for attr in ['x', 'px', 'y', 'py', 'zeta', 'delta']:
        assert np.allclose(
            getattr(p_no_slices, attr),
            getattr(p_with_slices, attr),
            atol=1e-14,
            rtol=0,
        )