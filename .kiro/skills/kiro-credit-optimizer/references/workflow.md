# Efficient engineering workflow

## Plan

Define one outcome and its acceptance checks. Assess complexity, repository size, uncertainty and expected retries. Use the current budget as a constraint to discuss scope, not as permission to skip checks. Default phase allocations distribute the spendable project budget: discovery 10%, planning 15%, implementation 45%, testing 20%, review 10%. Keep the reserve separate.

For a small documentation change, reuse existing conventions and run focused link/format checks. For authentication, data integrity or cross-service work, budget for security review, integration checks and broader tests. Never infer risk solely from diff size.

## Estimate

The optional CLI uses transparent, deliberately uncalibrated planning weights until at least three comparable verified task intervals exist. Match task type, complexity, repository size, model strategy and test scope. More phases, expected retries and uncertainty adjust the result. Strategy is a planning descriptor, not a model billing multiplier.

History only helps if the measured intervals represent comparable complete tasks. Do not use partial session claims as full-task training examples. Retain low confidence with sparse or self-reported data. A numeric range is a planning aid, not a statistically calibrated confidence interval.

## Execute

Search once with focused queries. Read the relevant files and their nearest repository instructions. Carry forward decisions rather than repeating discovery. Parallel agents need separate deliverables and a reason to justify context duplication. Use ordinary tools for calculations and repeatable transformations.

Choose validations according to the affected behavior and failure consequences. Start with focused checks and expand where risk or evidence warrants. Diagnose a failing check before rerunning; a smaller prompt does not repair a flawed hypothesis.

## Close

Record outcome, checks, scope changes and retry causes. If measured usage is available, compare it with the estimate and explain the attribution boundary. Reuse only the short context needed by the next session. Public reports must contain synthetic examples or deliberately reviewed, redacted data.
