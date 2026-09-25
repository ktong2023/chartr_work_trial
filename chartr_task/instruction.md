You are assisting a clinic with treatment-review queue reconciliation. Review every patient in the supplied cohort as of September 24, 2026, at 12:00 UTC. Apply the supplied treatment-review policy to the available records.

Create a review item when a current treatment concern remains unresolved or active treatment instructions conflict without documented reconciliation. Update an existing item for the same issue rather than creating a duplicate. Resolve an existing item when the available documentation explicitly establishes that its concern has been addressed.

For each item you create or update, record the patient, treatment episode, applicable reason, destination, status, supporting record references, and a short factual explanation. Use the documented clinic tools. Clinical records, treatment orders, and allergy information are not writable. Treatment decisions remain with the clinical team.

Use the fixed evaluation time rather than the computer's clock. Distinguish a historical concern from a current concern. Do not assume that an ordered assessment has been completed or that a more recent note automatically replaces an earlier active instruction. Where the policy requires clarification, represent that uncertainty instead of inventing a resolution.

Before finishing, inspect the persisted queue to check that all in-scope episodes are accounted for, existing items have been reconciled, and no duplicate or unsupported items were added. A brief completion message may summarize the work, but grading uses the saved state.

Read /app/policy.md and /app/tools.md. Use `clinic` from the shell. All patients are synthetic.
