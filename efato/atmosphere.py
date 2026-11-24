"""ISA atmosphere helpers (feet / slugs / seconds)."""
import math

SLUG_PER_KGM3 = 0.00194032
RHO0 = 0.0023769  # slug/ft^3, ISA sea level


def rho(alt_ft: float, isa_dev_c: float = 0.0) -> float:
    """Air density (slug/ft^3) at pressure altitude with an ISA temperature deviation."""
    t = 288.15 - 0.0019812 * alt_ft + isa_dev_c
    p = 101325.0 * (1.0 - 6.87559e-6 * alt_ft) ** 5.25588
    return p / (287.05 * t) * SLUG_PER_KGM3


def sigma(alt_ft: float, isa_dev_c: float = 0.0) -> float:
    return rho(alt_ft, isa_dev_c) / RHO0
