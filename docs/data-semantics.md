# Data and visual semantics

The interface uses color to communicate the state of a record, not a legal conclusion.

| Display state | Meaning | Source requirement |
|---|---|---|
| Source status | A status explicitly present in an authorized source record | Evidence reference required |
| Recorded status | A source explicitly records an investigation/charge state | Evidence reference required |
| Analytical review | A graph or extraction signal warrants analyst attention | No legal conclusion |
| Relevant association | A relationship is relevant to the current investigation context | Relationship record required |
| Unknown / unresolved | The system has no reliable status value | No inference |

Yellow/amber nodes mean **requires analytical review**. They do not mean “criminal” unless an authorized source explicitly records that status. Edge opacity and labels reflect confidence and relationship type; confidence is not a probability of guilt.

The API stores `status`, `record_state`, `confidence`, and evidence references separately so a visualization renderer can change without rewriting source data.
