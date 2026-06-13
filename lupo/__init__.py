"""Lupo — a coordination layer for agents + humans working at organisational scale.

The framework is domain-agnostic. This build ships one mission: a personal-shopper
"procurement org" that buys an outfit on Vinted within a budget, coordinating a
stylist, category buyers, a budget controller, a negotiator, simulated sellers, and
a human (the wearer/exec) over a human-in-the-loop channel.

Same lineage as the Lupo RFQ->quote project: spec compiler, escalate-vs-proceed,
budget/constraint solver, traceability, human gates — re-instantiated for a new domain.
"""
__version__ = "0.2.0"
