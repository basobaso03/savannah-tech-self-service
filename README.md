# Savannah Tech Innovations Self Service

AI customer self-service platform focused on business outcomes, marketing insight, and product decision support.

This concept is positioned like an early-stage product initiative, from strategy to working MVP:

- Problem discovery
- Product framing
- AI behavior design
- UX iteration
- Analytics and decision support

## Overview

A company-focused AI assistant and insights dashboard that helps teams:

- Deflect repetitive support questions
- Capture high-intent customer demand signals
- Identify unanswered questions that need content or sales follow-up
- Improve conversion paths with guided follow-up prompts

## Business Problem

Many growth-stage companies struggle with:

- Repetitive support requests (pricing, onboarding, location, support contact)
- Slow response times and inconsistent customer experience
- Poor visibility into what customers are asking for at scale
- Missed opportunities when AI cannot answer and conversations end abruptly

## Market Opportunity

- Support and marketing teams need shared visibility into customer intent
- AI copilots can reduce first-response pressure while improving consistency
- Conversation data can inform product messaging, pricing clarity, and growth priorities
- A focused vertical assistant can outperform generic chat for conversion-critical questions

## Product Solution

Savannah Tech Innovations Self Service combines:

- Customer chat assistant grounded on company knowledge
- Policy guardrails for domain-specific answering
- Structured fallback for missing information with marketing handoff
- Suggested next-question buttons to guide user journeys
- Admin analytics dashboard for trend detection and decision-making

## Product Thesis

If customer conversations are captured, structured, and fed back into decision-making loops, then:

- support load decreases,
- marketing gets clearer demand signals,
- and customer progression improves from question to action.

## Case Study: Problem => Solution => Results

### Problem

- Customer questions were repetitive and manually handled
- Follow-up intent was not structured for business use
- AI responses could fail on important commercial intents
- Leadership had no live view of customer demand patterns

### Solution

- Built a retrieval-driven assistant using company documentation
- Added deterministic handling for high-value intents (pricing, support, location)
- Designed follow-up suggestions to reduce dead-end interactions
- Implemented global analytics (categories, top questions, unresolved asks, exports)
- Iterated mobile UX (fixed composer, sidebar drawer, internal scroll behavior)

### Results

- More consistent handling of core customer intents
- Better conversation progression through guided prompt buttons
- Actionable admin visibility into customer needs and content gaps
- A reusable blueprint for business-first AI customer support

## MVP Scope

- Customer chat experience with session handling and guided prompts
- AI response policy with deterministic handling for key intents
- Knowledge ingestion pipeline for company documents
- Admin insights dashboard and CSV export for analysis

## Scope and Responsibilities

- Product design and scope definition
- Knowledge design and ingestion strategy
- AI policy and fallback behavior design
- Chat UX and admin dashboard UX
- Iterative debugging based on real conversation failures

## Product Development Process

### Customer Discovery

- Captured user pain points in response quality, discoverability, and mobile usability

### Problem Framing

- Reframed the project from “chatbot build” to “customer journey and insight engine”

### Solution Exploration

- Compared pure model responses vs retrieval-grounded, policy-constrained architecture

### MVP Build

- Delivered chat, starter onboarding prompts, suggestion chips, and admin analytics

### Iteration and Improvements

- Fixed intent drift in follow-ups
- Refined support/location/pricing routing
- Improved UI behavior for small screens and cancellation flow

## Key Product Decisions

- Keep secrets server-side only
- Keep frontend lightweight and interaction-focused
- Treat unanswered intents as business signals, not failures
- Prefer deterministic handling for high-stakes commercial intents

## Stack (Execution Layer)

- Backend: FastAPI
- LLM + embeddings: Gemini
- Vector storage/retrieval: Supabase
- Frontend: React + Vite
- Analytics: Structured event logging + dashboard summaries

## Repository Map

- Backend API/policy: [app](app)
- Frontend app: [frontend](frontend)
- Knowledge docs: [docs](docs)
- Ingestion pipeline: [ingest_company_data.py](ingest_company_data.py)
- Dependency list: [requirements.txt](requirements.txt)

## Run Locally

### Backend

Command from [How to start the system.txt](How%20to%20start%20the%20system.txt):

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

### Frontend

From [frontend](frontend):

npm install
npm run dev

## Concept Value

This concept demonstrates:

- Translate ambiguous business pain into clear product strategy
- Build practical AI systems with guardrails and measurable value
- Prioritize user experience and iterate quickly from real feedback
- Connecting technical implementation to marketing and growth outcomes

## Go-To-Market Direction

- Start with high-frequency support intents: pricing, onboarding, support channels, locations
- Use analytics to identify unanswered demand and update content quickly
- Position as a self-service + insight layer for service-led businesses
- Expand with role-based workflows for support, marketing, and leadership

## Next Improvements

- Session-level topic memory scoring for stronger follow-up continuity
- A/B testing for onboarding prompts and suggestion chips
- Role-based admin views (support, marketing, leadership)
- Deeper funnel and conversion analytics
