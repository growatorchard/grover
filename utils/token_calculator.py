from config.settings import INPUT_COST_PER_MILLION, OUTPUT_COST_PER_MILLION

def calculate_token_costs(token_usage):
    # Extract token counts
    prompt_tokens = token_usage.get("prompt_tokens", 0)
    completion_tokens = token_usage.get("completion_tokens", 0)

    # Calculate costs
    input_cost = (prompt_tokens / 1_000_000) * INPUT_COST_PER_MILLION
    output_cost = (completion_tokens / 1_000_000) * OUTPUT_COST_PER_MILLION
    total_cost = input_cost + output_cost

    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    } 