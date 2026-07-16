# Interactive Setup Menu Improvements

## Summary of Changes

This document describes the improvements made to the Cyber Agent interactive setup script (`scripts/setup.py`) to enhance user experience with menu-driven selections.

## Changes Made

### 1. Tool Selection Menu (Already Existed)
- ✅ Arrow keys (↑/↓) for navigation
- ✅ Space bar to select/deselect tools
- ✅ Enter to confirm selection
- ✅ Pre-selects already installed tools
- ✅ Shows tool categories and descriptions

### 2. Docker/Kali Container Menu (Already Existed)
- ✅ Arrow keys for navigation
- ✅ Enter to select option
- ✅ Clear explanation of benefits

### 3. LLM Provider Selection Menu (Already Existed)
- ✅ Arrow keys for navigation
- ✅ Enter to select provider
- ✅ Options: Ollama, OpenAI, Anthropic, Groq, Custom

### 4. **NEW: Interactive Ollama Model Selection Menu**
The `configure_ollama()` function now uses a fully interactive menu:

#### Features:
- **Auto-detects installed models**: Shows all Ollama models already on your system
- **Recommended models**: Displays curated list of models compatible with Cyber Agent (7B-32B range):
  - qwen2.5-coder:7b, 14b, 32b
  - llama3.2:3b, llama3.1:8b
  - mistral:7b
  - codellama:7b
  - deepseek-coder:6.7b
  - phi3:mini

#### Navigation:
- **↑/↓ arrows**: Move through the list
- **SPACE**: Select models to pull (for recommended models not yet installed)
- **ENTER**: Use the highlighted model (auto-pulls if not installed)
- **P**: Pull all selected models at once
- **C**: Enter a custom model name manually
- **B**: Go back to provider selection

#### User Flow:
1. If models are installed → shown in green section at top
2. Recommended models shown below with status indicators:
   - ✓ = Already installed
   - ☐ = Available to pull
   - ☑ = Selected for pulling (blue)
3. Press ENTER on any model to use it immediately
4. Press SPACE on multiple models, then P to batch-pull them
5. If no models installed, user can still choose from recommended or enter custom

### 5. **NEW: Interactive API Provider Model Selection Menu**
The `configure_api_provider()` function now uses an interactive menu for model selection:

#### Features:
- **Fetches available models** from the provider's API
- **Displays up to 20 models** in a scrollable list
- Shows total count if more than 20 models available

#### Navigation:
- **↑/↓ arrows**: Move through the model list
- **ENTER**: Select the highlighted model
- **C**: Enter a custom model name not in the list
- **B**: Go back to provider selection

#### Supported Providers:
- **OpenAI**: Fetches all GPT models from API
- **Anthropic**: Shows Claude models (claude-3-5-sonnet, claude-3-opus, claude-3-haiku)
- **Groq**: Fetches all available models from Groq API

#### User Flow:
1. User enters API key
2. System connects and fetches available models
3. Interactive menu displays models
4. User navigates with arrows and presses ENTER to select
5. Configuration saved with selected model

### 6. Welcome Message (Already Existed)
- ✅ Shows configuration summary
- ✅ Quick start guide
- ✅ Safety reminders

## Technical Implementation

### New Functions Added:

1. **`interactive_ollama_model_menu(installed_models, recommended)`**
   - Handles interactive Ollama model selection
   - Manages model pulling workflow
   - Supports batch operations

2. **`_interactive_api_model_menu(provider_info, api_key, models)`**
   - Handles interactive API provider model selection
   - Supports custom model entry
   - Graceful fallback to defaults

### Modified Functions:

1. **`configure_ollama()`**
   - Now calls `interactive_ollama_model_menu()` instead of text-based prompts
   - Enhanced recommended model list (9 models in 7B-32B range)

2. **`configure_api_provider()`**
   - Now calls `_interactive_api_model_menu()` when models are fetched
   - Better error handling and user feedback

## Benefits

1. **Consistent UX**: All menus now use the same arrow-key navigation pattern
2. **Visual Feedback**: Color-coded status indicators (green=installed, blue=selected, gray=available)
3. **Efficiency**: Users can batch-pull multiple Ollama models at once
4. **Flexibility**: Custom model entry always available as fallback
5. **Discoverability**: Users see all available options without memorizing numbers
6. **Professional Feel**: Modern terminal UI similar to popular CLI tools

## Usage

Run the setup script:
```bash
python scripts/setup.py
```

Navigate through all menus using:
- **Arrow keys** (↑/↓) to move up/down
- **Space bar** to select/deselect (where applicable)
- **Enter** to confirm selection
- **Letter shortcuts** (P, C, B) for specific actions

## Testing

All functions have been verified:
- ✅ Syntax check passed
- ✅ All imports successful
- ✅ No runtime errors detected

## Future Enhancements (Optional)

Potential future improvements:
- Add search/filter functionality for long model lists
- Show model sizes and requirements
- Cache fetched models to avoid repeated API calls
- Add progress bars for model pulling operations
