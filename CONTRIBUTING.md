# Contributing to Radiant Price

Thank you for your interest in contributing to Radiant Price! This guide explains how to contribute to the project.

## Types of Contributions

We welcome contributions in several areas:

### 1. Bug Fixes
- Report issues in the GitHub issue tracker
- Submit pull requests with fixes
- Include test cases and documentation updates

### 2. Feature Enhancements
- Improve report formatting
- Add new comparison capabilities
- Optimize performance
- Enhance OpenStack integration

### 3. Documentation
- Improve README.md with examples
- Clarify error messages
- Update CLAUDE.md for developer guidance
- Improve inline code documentation

### 4. Adding New Cloud Providers
- **See [PROVIDERS.md](PROVIDERS.md) for complete instructions**
- New providers must follow the standard interface:
  - `get_<provider>_flavor_prices()` - Compute instance pricing
  - `get_<provider>_storage_prices()` - Block storage pricing
- PROVIDERS.md contains real examples, best practices, and troubleshooting

## General Contribution Workflow

### 1. Fork and Branch
```bash
# Clone your fork
git clone https://github.com/yourname/radiant-price.git
cd radiant-price

# Create a feature branch
git checkout -b fix/your-fix-name
# or
git checkout -b feature/your-feature-name
```

### 2. Make Changes
- Follow PEP 8 style guidelines
- Add docstrings to new functions
- Update relevant documentation files

### 3. Test Your Changes
```bash
# Run syntax validation
python3 -m py_compile estimate.py update.py providers/*.py

# Test with dry-run when possible
python3 update.py yourprovider --dry-run

# Test cost comparison
python3 estimate.py --cloud software --comparison cheapest
```

### 4. Commit and Push
```bash
# Create clear commit messages
git add .
git commit -m "Fix: describe what you fixed"
git push origin fix/your-fix-name
```

### 5. Submit Pull Request
- Reference any related issues
- Describe what changed and why
- Include testing steps

## Code Style Guidelines

- **Python Version:** 3.7+
- **Format:** PEP 8
- **Type Hints:** Use `Dict`, `Optional`, etc. where appropriate
- **Docstrings:** Use triple-quoted strings with clear descriptions
- **Error Handling:** Print to stderr, exit with proper status codes

Example:
```python
def calculate_cost(cores: int, memory_gb: float) -> Optional[float]:
    """
    Calculate monthly cost for given resources.
    
    Args:
        cores: Number of CPU cores
        memory_gb: Memory in GB
        
    Returns:
        Monthly cost in USD or None if unavailable
    """
    if cores <= 0 or memory_gb <= 0:
        return None
    
    # Calculate cost...
    return cost
```

## Documentation Requirements

When you make changes, update the relevant documentation:

| Change Type | Files to Update |
|-------------|-----------------|
| New cloud provider | `PROVIDERS.md`, `CONTRIBUTING.md` |
| Provider behavior change | `PROVIDERS.md` |
| New report format | `README.md`, `CLAUDE.md` |
| New CLI option | `README.md`, `estimate.py` docstring |
| Pricing update logic | `CLAUDE.md` |
| New OpenStack feature | `CLAUDE.md`, `README.md` |

## Testing Checklist

Before submitting a pull request:

- [ ] Code passes `python3 -m py_compile`
- [ ] Changes tested manually
- [ ] Existing functionality not broken
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] No hardcoded paths or credentials added

### Testing for New Providers

If adding a new cloud provider, also verify:

- [ ] Both `get_*_flavor_prices()` and `get_*_storage_prices()` implemented
- [ ] Dry run works: `python3 update.py yourprovider --dry-run`
- [ ] Real update works: `python3 update.py yourprovider`
- [ ] Cost comparison works: `python3 estimate.py --cloud software --comparison yourprovider`
- [ ] Entry in PROVIDERS.md Quick Summary table
- [ ] Detailed section in PROVIDERS.md
- [ ] Example in CONTRIBUTING.md if pattern is new

## Resources

- **[PROVIDERS.md](PROVIDERS.md)** - Complete guide for adding cloud providers
- **[README.md](README.md)** - User guide and quick start
- **[CLAUDE.md](CLAUDE.md)** - Developer and AI assistant guide
- **[estimate.py](estimate.py)** - Main analysis tool (review docstrings)
- **[update.py](update.py)** - Pricing updater (review docstrings)

## Getting Help

- Review existing code in the repository
- Check PROVIDERS.md for provider-specific guidance
- Test with `--dry-run` flags when available
- Look at similar implementations in the codebase

## Questions?

Feel free to:
1. Open an issue on GitHub
2. Review existing code for examples
3. Check the documentation files listed above

---

**Last Updated:** November 2025
