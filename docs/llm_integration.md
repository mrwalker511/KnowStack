# LLM Integration

KnowStack is designed to feed LLM workflows with high-signal, low-token context
rather than dumping raw files. Two integration patterns are supported.

## Pattern 1: Context extraction (any LLM)

Generate a packed context block from any query and inject it into your prompt:

```bash
# Shell: pipe context into a prompt
CONTEXT=$(knowstack query "DEPENDENTS PaymentProcessor" --context)
echo "$CONTEXT" | claude -p "Given this context, what breaks if PaymentProcessor changes?"
```

```python
# Python: programmatic usage
from knowstack.config.loader import load_config
from knowstack.retrieval.query_engine import QueryEngine

config = load_config(repo_path=Path("."))
with QueryEngine(config) as engine:
    result = engine.query_dsl("FIND function WHERE tag = auth")
    context = engine.pack_context(result, max_tokens=4000)

# Inject `context` into your LLM system prompt or user message
```

## Pattern 2: Natural language query with LLM-generated DSL

Configure an LLM to handle NL→DSL translation:

```toml
# knowstack.toml
[knowstack]
llm_provider = "anthropic"
llm_model = "claude-haiku-4-5-20251001"
```

Set your API key:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Then use `--mode nl`:
```bash
knowstack query "How does authentication flow through this app?" --mode nl
```

Or programmatically:
```python
result = engine.query_nl("What writes to the customer database table?")
print(result.context)  # token-efficient context for your LLM
```

## Token efficiency

The context packer produces concise blocks (default budget: 6000 tokens):

```markdown
# Code Context
**Query:** authentication functions

## Function: `src.auth.service.AuthService.authenticate`
**Signature:** `async def authenticate(email: str, password: str) -> Token`
**Doc:** Authenticate a user and return a session token.
**File:** `src/auth/service.py:42-68`
**Relationships:**
  - CALLS → `_find_user`
  - CALLS → `_create_token`
  - CALLS → `Token.__init__`

---

## Method: `src.auth.service.AuthService._find_user`
...
```

This is typically 10-50x more token-efficient than including raw source files.

## Adjusting the budget

```python
# More context for complex questions
result = engine.query_hybrid("checkout pipeline")
context = engine.pack_context(result, max_tokens=12000)

# Tighter budget for API calls
context = engine.pack_context(result, max_tokens=2000)
```

## Using with the Anthropic SDK

```python
import anthropic
from knowstack.config.loader import load_config
from knowstack.retrieval.query_engine import QueryEngine

config = load_config(repo_path=Path("."))
client = anthropic.Anthropic()

with QueryEngine(config) as engine:
    result = engine.query_nl(user_question)
    context = engine.pack_context(result, max_tokens=4000)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=f"You are a code assistant. Use this context:\n\n{context}",
        messages=[{"role": "user", "content": user_question}],
    )
    print(response.content[0].text)
```
