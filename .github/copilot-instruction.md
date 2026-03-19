# Copilot Instructions for EduSmart Project

## 1. Project Overview

EduSmart is an AI-powered learning platform that helps students and self-learners efficiently study, summarize, and review knowledge using Large Language Models (LLMs).

The system allows users to upload study materials (PDF, DOCX, TXT) and interact with them through intelligent features such as:

- Document summarization
- Quiz generation
- Flashcards with spaced repetition
- Mind maps
- Study time tracking (Pomodoro)
- Learning goal management

---

## 2. Tech Stack

### Backend

- Python (FastAPI)
- PostgreSQL + pgvector
- MinIO (object storage)
- LLM API (Gemini)

### AI / RAG Pipeline

- Embedding model (e.g., text-embedding)
- Chunking strategy
- Vector search (pgvector)
- Prompt engineering for LLM

---

## 3. Architecture Guidelines

### General Principles

- Follow **Clean Architecture / DDD-lite**
- Avoid business logic inside controllers

---

## 4. Coding Conventions

### Python (Backend)

- Use type hints everywhere
- Use Pydantic for request/response validation
- Keep functions small and single-responsibility
- Prefer async/await for IO operations
- Use dependency injection (FastAPI Depends)

## 5. Feature-Specific Instructions

### 5.1 Document Processing

- Support PDF
- Extract text cleanly (remove noise)
- Chunk documents
- Store:
    - raw text
    - metadata (page, section)
    - embedding vector

### 5.2 RAG Pipeline

When implementing retrieval:

1. Embed user query
2. Retrieve top-k relevant chunks
3. Construct prompt with context
4. Call LLM to generate answer

Ensure:

- Context is concise
- Avoid hallucination by grounding in retrieved data

---

### 5.3 Summarization

- Support:
    - Full document
    - Page range
    - Keyword-based extraction
- Output should be:
    - Structured (headings, bullet points)
    - Clean HTML-friendly

---

### 5.4 Quiz Generation

- Generate:
    - Multiple choice (4 options, 1 correct)
- Allow configuration:
    - Difficulty (easy / medium / hard)
    - Number of questions
- Ensure:
    - No duplicate questions
    - Clear correct answer

---

### 5.5 Flashcards

- Extract key concepts automatically
- Format:
    - Front: term/question
    - Back: definition/answer
- Optionally enrich with images (via APIs)

---

### 5.6 Mind Map

- Generate hierarchical structure from document
- Output format:
    - Tree (JSON)
    - Convertible to SVG/graph

---

### 5.7 Pomodoro Timer

- Default: 25 min focus / 5 min break
- Store session history
- Allow customization

---

### 5.8 Learning Goals

- Support:
    - Daily / Weekly / Monthly goals
- Track progress
- Provide reminders (future feature)

---

## 6. API Design Guidelines

- Use RESTful conventions

## 7. Error Handling

- Always handle:
    - File parsing errors
    - LLM failures
    - Empty results from vector search

- Return meaningful error messages
- Avoid exposing internal stack traces

---

## 8. Performance Considerations

- Use background jobs for:
    - Embedding generation
    - Large document processing

- Cache frequent queries if needed
- Limit file size uploads

---

## 9. Security

- Use Google OAuth 2.0 for authentication
- Validate all inputs
- Protect file access (signed URLs if needed)
- Rate limit APIs

---

## 10. Copilot Behavior Guidelines

When generating code, Copilot should:

- Prefer clarity over cleverness
- Follow existing project structure
- Reuse existing services instead of duplicating logic
- Avoid introducing unnecessary dependencies
- Write production-ready code (not prototypes)

---

## 11. What to Avoid

- Do NOT put business logic in controllers
- Do NOT tightly couple services
- Do NOT hardcode API keys
- Do NOT return raw LLM responses without validation
- Do NOT skip error handling
