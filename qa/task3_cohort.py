"""Task 3 cohort (PRIVATE): the hand-authored core plus generated case families and background."""
from task3_cases import PATIENTS as CORE, EXTERNAL
from task3_families import generate

GENERATED, EXTERNALS = generate()
PATIENTS = CORE + GENERATED
EXTERNALS = {'EXTERNAL': EXTERNAL, **EXTERNALS}
assert len({p['key'] for p in PATIENTS}) == len(PATIENTS)
