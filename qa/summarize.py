"""Summarize saved attempts without conflating infrastructure errors and reward 0."""
import json
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'jobs/chartr')
results = []
for path in sorted(root.glob('*/*/result.json')):
    trial = path.parent
    result = json.loads(path.read_text())
    diagnostics = trial / 'verifier/diagnostics.json'
    diagnostics = json.loads(diagnostics.read_text()) if diagnostics.exists() else None
    termination = trial / 'controller/anthropic/termination.json'
    termination = json.loads(termination.read_text()) if termination.exists() else None
    reward = (result.get('verifier_result') or {}).get('rewards', {}).get('reward')
    exception = result.get('exception_info')
    validity = (diagnostics or {}).get('validity', 'evaluation_error' if exception or reward is None else 'valid')
    if exception and exception['exception_type'] != 'AgentTimeoutError':
        validity = 'evaluation_error'
    if termination and termination['validity'] != 'valid':
        validity = 'evaluation_error'
    results.append({'job': path.parent.parent.name, 'trial': trial.name, 'validity': validity,
                    'reward': reward if validity == 'valid' else None,
                    'termination': (termination or {}).get('reason'),
                    'exception': exception['exception_type'] if exception else None,
                    'evidence': str(trial.resolve())})
summary = {'attempts': results, 'valid': sum(r['validity']=='valid' for r in results),
           'invalid': sum(r['validity']!='valid' for r in results),
           'note': 'Development/QA attempts, not a model benchmark. No Anthropic credits used.'}
(root / 'verification-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
for result in results:
    print(result['job'], result['trial'], result['validity'], result['reward'], result['termination'] or '')
