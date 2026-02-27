# Spec: Premium Model Tier

## ADDED Requirements

### Requirement: Premium model swap on main client

ClaudeClient MUST support a `use_premium_model` flag in `call()` that switches to a premium model name while reusing the main SDK client.

#### Scenario: Premium model call

- **WHEN** `call()` is invoked with `use_premium_model=True` and `model_premium` is configured
- **THEN** the call MUST use `model_premium` as the active model
- **AND** the call MUST use the main client (not a separate client)
- **AND** the main SDK type MUST be used for API format

#### Scenario: Premium not configured — fallback to main

- **WHEN** `call()` is invoked with `use_premium_model=True` but `model_premium` is empty
- **THEN** the call MUST fall back to the main model
- **AND** behavior SHALL be identical to a normal (non-premium) call

#### Scenario: Priority — premium overrides light

- **WHEN** both `use_premium_model=True` and `use_light_model=True` are passed
- **THEN** premium MUST take priority
- **AND** the premium model SHALL be used

### Requirement: P5/P6 use premium when tier is premium

P5 (Build) and P6 (Optimize) phases MUST pass `use_premium_model=True` when `config.quality_tier == "premium"`.

#### Scenario: Premium tier build

- **WHEN** quality_tier is "premium" and model_premium is configured
- **THEN** P5 SKILL.md generation calls MUST use `use_premium_model=True`
- **AND** P6 optimization calls MUST use `use_premium_model=True`

#### Scenario: Standard tier build — no premium

- **WHEN** quality_tier is "standard" or "draft"
- **THEN** P5/P6 calls SHALL NOT use premium model
- **AND** behavior MUST be identical to current implementation

### Requirement: Config field

BuildConfig MUST include `claude_model_premium` field, populated from env var `CLAUDE_MODEL_PREMIUM`.

#### Scenario: Premium model configured

- **WHEN** `CLAUDE_MODEL_PREMIUM` env var is set (e.g., "claude-opus-4-6")
- **THEN** BuildConfig.claude_model_premium MUST contain that value

#### Scenario: Premium model not configured

- **WHEN** env var is not set
- **THEN** field MUST default to empty string
- **AND** premium calls SHALL fall back to main model
