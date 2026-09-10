"""Release gates shared by retrieval evaluation entrypoints."""


def validate_cases(cases: list[dict], *, exploratory: bool = False) -> None:
    if not cases:
        raise ValueError('an evaluation set must not be empty')
    ids = [row['query_id'] for row in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate query IDs')
    if any(row.get('validation_verdict') in ('wrong', 'rejected') for row in cases):
        raise ValueError('rejected cases cannot be scored; select a reviewed dataset release')
    if not exploratory and any(not row.get('validated_by') for row in cases):
        raise ValueError('unreviewed cases require --exploratory; they are not release evidence')
