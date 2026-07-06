# Poker Solver: Final Project

## Project description (AI Engineering course)

Poker Solver is a full-stack poker app (React + FastAPI + MongoDB) focused first on real game flow: players can host real-time online multiplayer tables over WebSockets, manage live sessions, track cash games, tournaments, debts, solve chip discrepancies, and view per-player statistics in one place. On top of the live-play system it adds poker tools such as equity simulations and saved hand analysis, with an AI layer built on Google Gemini that works with the hands played inside the app, generating persona-driven game recaps and providing street-by-street coaching on saved hands using RAG, grading each hero decision and identifying the biggest leak in the hand. The goal is a complete poker app built from a real player's perspective, combining game flow, player tracking, session management, and AI-based strategic analysis into one system.

## Mermaid diagram: `mermaid_final`

Main app flow, left to right.

```mermaid
flowchart LR
    User([User]) --> Auth[Login / Sign up] --> Home{{Home}}

    subgraph record["Add & Track Games"]
        direction TB
        GameSelect[Add New Game]
        CashGame["Cash game<br/>live session or finished"]
        TourneyGame["Tournament<br/>template or new"]
        ChipSolve[Chip discrepancy solver]
        GameSelect --> CashGame
        GameSelect --> TourneyGame
        CashGame --> ChipSolve
    end

    subgraph live["Live Online Tables"]
        direction TB
        LiveTable["Real-time WebSocket play<br/>create · quick play · join"]
        Voice[Voice commands]
        SaveHand[Save key hand]
        Settle[Settle & finalize]
        LiveTable --> Voice
        LiveTable --> SaveHand
        LiveTable --> Settle
    end

    subgraph tools["Tools"]
        direction TB
        Equity["Equity Calculator<br/>NLH · PLO4 · PLO5"]
        GamePlanner[Game planner page]
        Stats[Stats & milestones]
        Debts[Debt management]
    end

    subgraph history["Game History"]
        direction TB
        HistHome[Browse history]
        HCash[Cash games]
        HTourney[Tournaments]
        HHands[Key hands]
        HistHome --> HCash
        HistHome --> HTourney
        HistHome --> HHands
    end

    subgraph ai["🤖 AI Layer · Gemini"]
        direction TB
        Recap[Game recap note]
        Analysis[Hand analysis]
        RAG[RAG hand coach]
        Invite[n8n WhatsApp invites]
        Spot[Spot training]
    end

    %% Home fan-out (ordered top-to-bottom to match the columns)
    Home --> GameSelect
    Home --> LiveTable
    Home --> Equity
    Home --> GamePlanner
    Home --> Stats
    Home --> Debts
    Home --> HistHome
    Home --> Spot

    %% Play / record → history
    ChipSolve --> HCash
    TourneyGame --> HTourney
    Settle -->|seeds recorded game| GameSelect
    SaveHand --> HHands

    %% Feeds into the AI layer
    HCash --> Recap
    HHands --> Analysis
    HHands --> RAG
    GamePlanner --> Invite
```
