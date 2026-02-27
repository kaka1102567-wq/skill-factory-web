# multi-provider-light-model Specification

## Purpose
TBD - created by archiving change multi-provider-opus-tier. Update Purpose after archive.
## Requirements
### Requirement: Separate light model provider

ClaudeClient MUST support a separate API provider for the light model, configured via `base_url_light` and `api_key_light` parameters.

#### Scenario: Light model uses separate provider (DeepSeek)

- **WHEN** `base_url_light` and `api_key_light` are both provided
- **THEN** ClaudeClient MUST create a separate OpenAI-compatible SDK client for light model calls
- **AND** light model calls MUST use the separate client, not the main client

#### Scenario: Light model uses separate base_url but shared API key

- **WHEN** `base_url_light` is provided but `api_key_light` is empty
- **THEN** ClaudeClient MUST create a separate OpenAI client using the main API key with the light base_url

#### Scenario: Backward compatible — light uses main provider

- **WHEN** both `base_url_light` and `api_key_light` are empty
- **THEN** light model calls MUST use the main client (same as current behavior)
- **AND** no additional SDK client SHALL be created

### Requirement: Separate credit exhaustion tracking

ClaudeClient MUST track credit exhaustion separately for main and light providers.

#### Scenario: Light provider credit exhausted

- **WHEN** light model calls fail 3 times consecutively with credit errors
- **THEN** CreditExhaustedError MUST be raised for light provider
- **AND** main provider credit counter SHALL NOT be affected

#### Scenario: Main provider credit exhausted

- **WHEN** main/premium model calls fail 3 times consecutively with credit errors
- **THEN** CreditExhaustedError MUST be raised for main provider
- **AND** light provider credit counter SHALL NOT be affected

### Requirement: Config and env var support

BuildConfig MUST include `claude_base_url_light` and `claude_api_key_light` fields, populated from env vars `CLAUDE_BASE_URL_LIGHT` and `CLAUDE_API_KEY_LIGHT`.

#### Scenario: Env vars present

- **WHEN** `CLAUDE_BASE_URL_LIGHT` and `CLAUDE_API_KEY_LIGHT` env vars are set
- **THEN** BuildConfig fields MUST be populated with those values

#### Scenario: Env vars absent

- **WHEN** env vars are not set
- **THEN** fields MUST default to empty string
- **AND** pipeline MUST behave identically to current behavior

