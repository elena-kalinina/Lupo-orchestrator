# Lupo — video voiceover (read aloud, ~85s)

Read straight through. Timings are approximate. **[do]** notes are stage directions,
not spoken. Centred on the **Tomorrowland** run (the reallocation beat); a one-line
**negotiate** variant is given if you record the brunch run instead.

---

## Part 1 — Architecture (~22s)
**[do: full-screen the architecture diagram; point as you name each module]**

"This is Lupo — a coordination layer for agents *and* humans.

Most AI agents today are a single model calling tools. The hard part — and the real
value — is the layer above: coordinating a whole team of agents and a person, together.

Here's the architecture. At the centre is the **Coordinator**. It doesn't shop, style,
or haggle — it *coordinates*. It routes work, it holds the shared ledger that every
agent reads and writes, and it runs one policy: act on its own, confirm with me, or
ask me.

Around it: a **human-in-the-loop channel** — voice, WhatsApp, or web. A **swappable
roster** of specialist agents — a stylist, buyers, procurement, a negotiator. And a
**model-arbitration loop**: a small, cheap model does the routine work, and only the
hard cases escalate to Gemini.

Everything domain-specific lives in one swappable layer at the bottom. That's the whole
idea — the core never changes."

## Part 2 — Live demo (~50s)
**[do: switch to the canvas; press Play; let the feed breathe on each escalation]**

"Now watch it run. The brief: a Tomorrowland outfit, eighty euros.

The stylist proposes a look and pings me — and I tweak it: mesh top, a bit more sparkle.

Then procurement proposes how to split the budget across the four pieces — and this is
a deliberate checkpoint: I approve that split *before* anything gets bought.

Now the buyers search Vinted in parallel. These listings are real — French, Dutch,
Italian, German — and the small model pulls structured attributes out of that messy
text. **[do: point to a 'GLiNER unsure → Gemini' tag]** When it isn't confident, watch
— it escalates that one listing up to Gemini.

And here's the moment that matters. **[do: pause on the boots escalation]** The platform
boots are the hero of the look, but they're sixteen euros over their slice. The
Coordinator doesn't just overspend — it asks me: negotiate, or stretch? I say stretch —
and procurement *reallocates* sixteen euros of slack from the other categories. Total
stays under eighty. Nothing overspent.

And the finish is honest: the four finds come from four sellers in four countries — so
three of them ship, paid online, and only the local Munich pair becomes an in-person
pickup, with the tram and the exact cash for that one item."

> *Negotiate variant (brunch run):* "…it asks me: negotiate, or stretch? I say negotiate —
> and the negotiator agent haggles the seller down from thirty-two euros to twenty-six,
> live. Six euros saved, and the outfit lands under budget."

## Part 3 — The close (~13s)
**[do: back to the diagram; let the 'consumer → industrial' swap arrow show]**

"So that's Lupo. The same move repeats at every level — agent to human, cheap model to
frontier model, buyer to seller.

And because all of that lives in the core, you swap the roster and the catalog, and the
outfit shopper becomes industrial technical sales — RFQs, product catalogs, buyers and
sellers. The coordination layer is the product. The outfit was just the demo."

---

### 60-second cut
Trim Part 1's middle paragraph to one line ("a human channel, a swappable agent roster,
and a cheap-model-to-Gemini loop"), and drop the negotiate variant. Keep the boots
escalation and the swap close — they carry the message.
