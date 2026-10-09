## Installation

Clone the repo:

```sh
git clone git@github.com:curiousily/legal-mentor.git
cd legal-mentor
```

Install the dependencies (requires Poetry):

```sh
poetry install
```


```
### Ingestor

Extracts text from PDF documents and creates chunks (using semantic and character splitter) that are stored in a vector databse

 ### Retriever

Given a query, searches for similar documents, reranks the result and applies LLM chain filter before returning the response.

### QA Chain

Combines the LLM with the retriever to answer a given user question.
