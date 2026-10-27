"""Protected-main integration through one recorded PR; never bypass rules."""
import time

import ship as core
from ship_release import capture, read_json
from ship_state import Blocked, Journal


def integrate(checkout, remote, main, journal: Journal, timeout=1800):
    candidate = journal.data.setdefault('candidate_sha', journal.data['validated_sha'])
    branch = 'ship/' + journal.data['run_id']
    journal.save(candidate_sha=candidate, candidate_branch=branch, phase='pull_request')
    operations = journal.data.get('operations', {})
    if operations.get('candidate-push', {}).get('status') in ('done', 'uncertain'):
        state = core.verify_remote(checkout, remote, branch)
        if state.get('remote_sha') != candidate:
            raise Blocked('candidate push outcome is not confirmed; no push repeated')
        journal.done('candidate-push', sha=candidate)
    else:
        scan = core.scan(checkout, remote)
        if not scan['ok']:
            raise Blocked(scan['summary'])
        journal.intent('candidate-push')
        try:
            core.run(checkout, 'push', remote, f'{candidate}:refs/heads/{branch}', timeout=180, env=core.NET_ENV)
        except (OSError, TimeoutError):
            pass
        if core.verify_remote(checkout, remote, branch).get('remote_sha') != candidate:
            raise Blocked('candidate push not confirmed; reconcile before continuing')
        journal.done('candidate-push', sha=candidate)
    def existing():
        rows = read_json(['gh', 'pr', 'list', '--head', branch, '--base', main, '--state', 'all',
                          '--json', 'number,headRefOid,state,url,mergeCommit'], checkout)
        if not isinstance(rows, list) or len(rows) > 1:
            raise Blocked('PR identity is ambiguous')
        if rows and rows[0].get('headRefOid') != candidate:
            raise Blocked('PR head differs from the validated candidate')
        return rows[0] if rows else None
    pr = existing()
    if not pr:
        if journal.intent('pr-create'):
            result = capture(['gh', 'pr', 'create', '--head', branch, '--base', main,
                              '--title', journal.data.get('summary', 'Merge repository work'),
                              '--body', 'Checks passed.'], checkout)
            if result.returncode:
                raise Blocked('PR creation did not confirm success; reconcile its recorded head before any new operation')
        pr = existing()
        if not pr:
            raise Blocked('created PR could not be confirmed')
    journal.done('pr-create', number=pr['number'], url=pr.get('url'))
    journal.save(pr_number=pr['number'], pr_url=pr.get('url'))
    if pr['state'] == 'CLOSED':
        raise Blocked('release PR is closed without merging; no replacement PR created')
    if pr['state'] != 'MERGED':
        operation = journal.data.get('operations', {}).get('pr-merge', {})
        if operation.get('status') != 'uncertain' and journal.intent('pr-merge'):
            result = capture(['gh', 'pr', 'merge', str(pr['number']), '--merge', '--auto',
                              '--match-head-commit', candidate], checkout)
            if result.returncode:
                raise Blocked('PR merge did not confirm success; read PR/check status instead of repeating it')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = read_json(['gh', 'pr', 'view', str(pr['number']), '--json',
                               'state,headRefOid,mergeCommit,mergeStateStatus,url'], checkout)
            if state.get('headRefOid') != candidate:
                raise Blocked('PR head changed while waiting; do not merge unvalidated work')
            if state['state'] == 'MERGED':
                pr = state
                break
            if state['state'] == 'CLOSED':
                raise Blocked('release PR closed without merging')
            journal.save(pr_status=state)
            time.sleep(min(5, max(0, deadline - time.monotonic())))
        else:
            raise Blocked('PR checks, review or merge remain pending; resume read-only monitoring without bypassing rules')
    merged = pr.get('mergeCommit', {}).get('oid')
    if not merged:
        raise Blocked('merged PR has no confirmed merge commit')
    journal.done('pr-merge', sha=merged)
    if core.run(checkout, 'fetch', '--quiet', remote, main, timeout=60, env=core.NET_ENV).returncode:
        raise Blocked('cannot fetch the merged main commit')
    if not core.ok(checkout, 'merge-base', '--is-ancestor', merged, f'{remote}/{main}'):
        raise Blocked('remote main does not contain the recorded PR merge')
    if core.run(checkout, 'merge', '--ff-only', f'{remote}/{main}', timeout=300).returncode:
        raise Blocked('cannot fast-forward local main to the merged PR; preserve local commits and inspect')
