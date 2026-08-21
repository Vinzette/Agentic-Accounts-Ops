/** Human names and explanations for the pipeline's nodes, shared by the stream and the diagram. */
export const NODE_LABELS: Record<string, string> = {
  load_data: 'Reading the account data',
  generate_briefing: 'Writing the briefing',
  validate_output: 'Checking every citation against the data',
  persist_run: 'Recording the run',
  save_briefing: 'Done',
}

export const NODE_NOTES: Record<string, string> = {
  load_data:
    'Validates the record before anything is spent on it. A malformed account fails here, with no API call made.',
  generate_briefing:
    'One call to the model with the system prompt and the account data. On a retry, the specific failures from the last attempt are attached.',
  validate_output:
    'Every figure cited in brackets has to appear in the source data. Fabricated numbers are caught here.',
  persist_run:
    'Writes the run to the log — the input it ran on, the raw response, and whether it grounded.',
  save_briefing: 'Renders the briefing the account manager reads.',
}
