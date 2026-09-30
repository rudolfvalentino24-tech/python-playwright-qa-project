from flask import g


# Standard OpenAI API text-token pricing in USD per 1M tokens.
# Long-context pricing applies when input exceeds 272K tokens.
MODEL_PRICING = {
    "gpt-5.6-luna": {
        "short": {"input": 0.20, "cached": 0.02, "output": 1.20},
        "long": {"input": 0.40, "cached": 0.04, "output": 1.80},
    },
    "gpt-5.6-terra": {
        "short": {"input": 2.00, "cached": 0.20, "output": 12.00},
        "long": {"input": 4.00, "cached": 0.40, "output": 18.00},
    },
    "gpt-5.6-sol": {
        "short": {"input": 4.00, "cached": 0.40, "output": 20.00},
        "long": {"input": 8.00, "cached": 0.80, "output": 30.00},
    },
}


def _value(obj, name, default=0):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _usage_details(response, model):
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    input_tokens = int(_value(usage, "input_tokens", 0) or 0)
    output_tokens = int(_value(usage, "output_tokens", 0) or 0)
    total_tokens = int(_value(usage, "total_tokens", input_tokens + output_tokens) or 0)

    input_details = _value(usage, "input_tokens_details", None)
    cached_tokens = int(_value(input_details, "cached_tokens", 0) or 0)
    cached_tokens = max(0, min(cached_tokens, input_tokens))
    uncached_tokens = input_tokens - cached_tokens

    model_key = (model or "").strip().lower()
    pricing = MODEL_PRICING.get(model_key)
    cost_usd = None
    context_tier = "Unknown"
    rates = None

    if pricing:
        context_key = "long" if input_tokens > 272_000 else "short"
        context_tier = "Long context" if context_key == "long" else "Short context"
        rates = pricing[context_key]
        cost_usd = (
            uncached_tokens * rates["input"]
            + cached_tokens * rates["cached"]
            + output_tokens * rates["output"]
        ) / 1_000_000

    return {
        "model": model or "Unknown model",
        "input_tokens": input_tokens,
        "cached_tokens": cached_tokens,
        "uncached_tokens": uncached_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "cost_display": f"${cost_usd:.6f}" if cost_usd is not None else "Pricing unavailable",
        "context_tier": context_tier,
        "rates": rates,
    }


def record_usage(response, model):
    details = _usage_details(response, model)
    if details is not None:
        g.ai_usage = details
    return details


class _ResponsesProxy:
    def __init__(self, responses):
        self._responses = responses

    def parse(self, *args, **kwargs):
        response = self._responses.parse(*args, **kwargs)
        record_usage(response, kwargs.get("model", ""))
        return response

    def __getattr__(self, name):
        return getattr(self._responses, name)


class _OpenAIProxy:
    def __init__(self, original_openai, *args, **kwargs):
        self._client = original_openai(*args, **kwargs)
        self.responses = _ResponsesProxy(self._client.responses)

    def __getattr__(self, name):
        return getattr(self._client, name)


def _tracked_factory(original_openai):
    def create_client(*args, **kwargs):
        return _OpenAIProxy(original_openai, *args, **kwargs)

    create_client._test_hub_ai_usage_wrapped = True
    return create_client


def _usage_panel():
    return '''
{% if g.ai_usage %}
<div style="margin:12px 0 18px;padding:13px 15px;border:1px solid #cddcf8;border-radius:12px;background:#f5f8ff;color:#294a7a;font-size:12px;line-height:1.5">
  <strong style="font-size:13px">💳 AI usage — this generation</strong><br>
  Model: <strong>{{ g.ai_usage.model }}</strong> ·
  Input: <strong>{{ '{:,}'.format(g.ai_usage.input_tokens) }}</strong> tokens ·
  Cached: <strong>{{ '{:,}'.format(g.ai_usage.cached_tokens) }}</strong> ·
  Output: <strong>{{ '{:,}'.format(g.ai_usage.output_tokens) }}</strong> ·
  Total: <strong>{{ '{:,}'.format(g.ai_usage.total_tokens) }}</strong><br>
  Estimated API cost: <strong>{{ g.ai_usage.cost_display }}</strong> · {{ g.ai_usage.context_tier }}
  <div style="margin-top:4px;color:#68778b">Estimate uses standard text-token rates returned for the selected model. Actual billing can differ for cache writes, regional processing or another service tier.</div>
</div>
{% endif %}
'''


def apply_ai_usage_tracking(ai_designer, ai_automation):
    for module in (ai_designer, ai_automation):
        current = module.OpenAI
        if not getattr(current, "_test_hub_ai_usage_wrapped", False):
            module.OpenAI = _tracked_factory(current)


def apply_ai_usage_ui(ai_designer, bdd_sync):
    panel = _usage_panel()

    designer_marker = '<form method="post" action="{{ url_for(\'ai_create_selected_cases\') }}">'
    if "AI usage — this generation" not in ai_designer.REVIEW_PAGE_HTML and designer_marker in ai_designer.REVIEW_PAGE_HTML:
        ai_designer.REVIEW_PAGE_HTML = ai_designer.REVIEW_PAGE_HTML.replace(
            designer_marker,
            panel + designer_marker,
            1,
        )

    automation_marker = '<p style="font-size:13px;color:#41526c"><strong>Summary:</strong> {{ proposal.summary }}</p>'
    if "AI usage — this generation" not in bdd_sync.AUTOMATION_PAGE_HTML and automation_marker in bdd_sync.AUTOMATION_PAGE_HTML:
        bdd_sync.AUTOMATION_PAGE_HTML = bdd_sync.AUTOMATION_PAGE_HTML.replace(
            automation_marker,
            automation_marker + panel,
            1,
        )
