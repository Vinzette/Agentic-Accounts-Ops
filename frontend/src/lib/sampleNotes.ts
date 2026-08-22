/**
 * Realistic messy input for the Paste tab.
 *
 * Not the example from the extraction prompt — the model has seen that one with
 * a worked answer attached, so it would extract well for the wrong reason. And
 * deliberately not the shape of any seeded account: one exercises the
 * leading-vs-lagging tie-break, the other exercises how thin data degrades.
 */
export interface SampleNote {
  label: string
  note: string
  text: string
}

export const SAMPLE_NOTES: SampleNote[] = [
  {
    label: 'Voice memo',
    note: 'Spoken numbers, and the signals pull against each other',
    text: `[voice memo — auto-transcribed]

right so, Calder Mills, um, catch-up after the exec review yesterday.

The numbers actually look great on paper? They've gone from about one point nine
to two point four million this year, biggest jump in the region I think. NPS came
back a nine. And apparently their CEO namechecked us in a town hall, which, you
know, doesn't hurt.

But — and this is the bit bothering me — when I pulled usage before the call,
daily actives are down around thirty one percent of seats. That was in the
seventies eighteen months ago. Nobody internally has flagged it because the
revenue keeps climbing, so it just hasn't come up.

Uh, they also bought the analytics tier back in the spring and haven't switched
it on. Which I suspect is related, honestly.

Contract isn't up for another fourteen months so there's no urgency their side.
That's sort of the problem.`,
  },
  {
    label: 'Slack thread',
    note: 'Almost nothing to go on — see how it degrades',
    text: `#gam-handover

priya  10:42
anyone got context on Vellum Foods before I call them thursday? inherited this
one off Sam when he left

dan  10:51
not much I'm afraid — Growth tier, think it's somewhere around 400k? went live
maybe a year ago

priya  10:52
any idea who I'd even be talking to

dan  10:55
no sorry. Sam would've known. there's nothing in the notes`,
  },
]
