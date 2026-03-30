# Fase 4 — Integrazione Claude AI Sentiment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans

**Goal:** Implementare il modulo sentiment che interroga Claude API con web search per ottenere un'analisi di mercato in tempo reale, e integrarlo come filtro finale nella CombinedStrategy.

**Architecture:** `sentiment/claude_sentiment.py` espone `ClaudeSentiment.analyze()` che chiama Claude API con web search tool, chiede un'analisi sentiment su BTC e parsa la risposta JSON. La `CombinedStrategy` viene estesa con un parametro opzionale `sentiment_result` in `generate_signal()` che filtra i segnali in base a score e confidence.

**Tech Stack:** Python 3.10+, anthropic SDK, pytest

---

### Task 1: Implementare ClaudeSentiment

### Task 2: Integrare sentiment nella CombinedStrategy

### Task 3: Verifica finale
