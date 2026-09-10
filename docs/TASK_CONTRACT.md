# Task contract

A computational or bench biologist triages cancer-genomics literature for a specific variant and
condition before a lab meeting or written research brief. The proposed product returns a concise,
auditable evidence brief with exact supporting source spans and visible uncertainty.

Current corpus: the PMC OA snapshot identified by `corpus/manifest.csv` and `corpus/run_info.json`.
Evaluation exclusions are a separate corpus view in `eval/held_out/held_out_pmcids.csv`.
HTTP supports retrieval and opt-in validated synthesis with source spans. The researcher
interface and live quality validation remain open. Do not present the service as a completed
product or a clinically validated system.

Correct output should report the requested association accurately, cite each factual claim,
expose relevant conflicting evidence and distinguish absence of retrieved support from absence
of an association. Clinical diagnosis, treatment or prognosis for an identified person is outside
scope. Input and output remain subject to researcher review.

Targets to validate, not achieved claims: p95 end-to-end at most 6 seconds, first useful output
at most 1.5 seconds and cost at most $0.05 per query under a stated workload. Define generation
TTFT separately from retrieval's first NDJSON line. Track unsupported claims, omitted important
evidence, false abstentions and time to a useful brief. Judge thresholds and label interpretation
are developed with the user, not inferred from a target rate.

Keep article license/version and corpus date visible in downstream exports. Local free inference
and hardware do not establish the economics of a hosted product.
