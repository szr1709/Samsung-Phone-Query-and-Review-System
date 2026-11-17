# Samsung Phone Query and Review System

An AI-powered Samsung smartphone information and review system that combines web scraping, PostgreSQL, ChromaDB, hybrid retrieval, a two-agent architecture, and a FastAPI-based chatbot interface.

## Project Overview

This project collects Samsung smartphone specifications and prices from GSMArena, stores the information in PostgreSQL, and makes it searchable through a conversational AI system.

The system uses two agents:

1. **Specification Retrieval Agent** – retrieves relevant phone information using SQL and semantic search.
2. **Review Generation Agent** – uses the retrieved information to generate detailed answers, reviews, and comparisons with a local language model.

A FastAPI backend exposes the system through an API, while a web-based chat interface allows users to interact with it.

## Features

- Scrapes up to 15 Samsung smartphones from GSMArena.
- Extracts phone specifications, release information, and available prices.
- Stores structured information in PostgreSQL.
- Indexes phone specifications in ChromaDB.
- Uses Ollama embeddings for semantic retrieval.
- Combines SQL and semantic retrieval for hybrid search.
- Uses a two-agent retrieval and review-generation architecture.
- Generates phone reviews and comparisons using a local LLM.
- Provides REST API endpoints through FastAPI.
- Includes a browser-based chatbot interface.
- Supports interactive questions about phone specifications, features, and prices.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Web Scraping | Requests, BeautifulSoup |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Vector Database | ChromaDB |
| Embedding Model | nomic-embed-text |
| Language Model | qwen2.5:3b |
| LLM Runtime | Ollama |
| Backend API | FastAPI |
| API Server | Uvicorn |
| Frontend | HTML, CSS, JavaScript |


## Project Structure

```text
Samsung-Phone-Query-and-Review-System/
│
├── agents/
│   ├── crew.py
│   ├── tools.py
│   ├── run_review.py
│   └── __init__.py
│
├── api/
│   ├── main.py
│   └── __init__.py
│
├── chatbot/
│   ├── chat.py
│   ├── chroma_store.py
│   ├── hybrid_retriever.py
│   ├── indexer.py
│   ├── ollama_client.py
│   ├── prompt.py
│   ├── retriever.py
│   ├── sql_retriever.py
│   └── __init__.py
│
├── database/
│   ├── connection.py
│   ├── create_database.py
│   ├── create_tables.py
│   ├── models.py
│   └── __init__.py
│
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
│
├── scraper/
│   ├── gsmarena_scraper.py
│   ├── gsmarena_specification_scraper.py
│   ├── run_scraper.py
│   └── __init__.py
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Prerequisites

Install the following before running the project:

- Python 3.10 or newer
- PostgreSQL
- Ollama
- Git

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/szr1709/Samsung-Phone-Query-and-Review-System.git
cd Samsung-Phone-Query-and-Review-System
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
DB_USER=your_postgresql_username
DB_PASSWORD=your_postgresql_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=samsung_phone_db
```

Replace the example values with your PostgreSQL configuration.

Never commit your actual `.env` file or database credentials.

### 5. Create the PostgreSQL database

```powershell
python -m database.create_database
```

### 6. Create database tables

```powershell
python -m database.create_tables
```

## Ollama Setup

Install Ollama and make sure its service is running.

Pull the required models:

```powershell
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

The project uses:

- `qwen2.5:3b` for response and review generation.
- `nomic-embed-text` for generating embeddings used in semantic retrieval.

The default Ollama address is:

```text
http://localhost:11434
```

## Data Collection

The project includes an all-in-one scraper setup script.

Run:

```powershell
python -m scraper.run_scraper
```

## Build the Vector Database

After collecting phone specifications, index them in ChromaDB:

```powershell
python -m chatbot.indexer
```

The indexer creates or updates the persistent ChromaDB collection:

```text
samsung_phones
```

ChromaDB files are generated locally in:

```text
database/chroma_db/
```

This directory is excluded from Git. Run the indexer again after setting up the project to rebuild the vector index from PostgreSQL.

## Running the Multi-Agent Review System

To test the two-agent system from the terminal:

```powershell
python -m agents.run_review
```

Enter a question about a Samsung smartphone when prompted.

## Running the FastAPI Application

Start the API server:

```powershell
uvicorn api.main:app --reload
```

Open the chatbot frontend:

```text
http://127.0.0.1:8000/
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Opens the chatbot frontend |
| GET | `/health` | Checks API health |
| POST | `/review` | Retrieves information and generates a phone review |

### Example API Request

**POST** `/review`

```json
{
  "question": "Write a detailed review of Samsung Galaxy A57."
}
```

### Example Response Structure

```json
{
  "question": "Write a detailed review of Samsung Galaxy A57.",
  "review": "Generated phone review..."
}
```

## Example Questions

- What is the price of Samsung Galaxy A57?
- What is the battery capacity of Galaxy S26 FE?
- Write a detailed review of Galaxy A57.
- Compare Galaxy A57 and Galaxy S26 FE.
- Which phone has the better display?
- Which Samsung phone has better performance?

## Data and Index Notes

The project stores structured smartphone information in PostgreSQL and semantic vectors in ChromaDB.

The current development dataset contains 15 Samsung smartphones and 690 indexed specification records.

The ChromaDB vector index is generated locally and is not included in the repository. It can be rebuilt using the indexing command after the PostgreSQL data has been populated.

## Notes

- Phone prices and specifications are based on scraped source information and may change over time.
- The generated AI responses depend on the retrieved information and may require independent verification.
- Ollama must be running locally for review generation and embedding operations.
- PostgreSQL must be accessible before running database-dependent components.
- GSMArena is the source used for smartphone listing and specification collection.

## Author

Developed as a Samsung smartphone information retrieval and AI-powered review system project.