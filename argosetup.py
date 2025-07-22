import argostranslate.package
import argostranslate.translate

from errorlogger import error_logger


def setup_german_to_english():  # Changed from setup_spanish_to_english
    """Install German to English translation model if not already installed."""
    try:
        # Update package index
        argostranslate.package.update_package_index()
        
        # Get available packages
        available_packages = argostranslate.package.get_available_packages()
        
        # Find German to English package
        german_to_english_package = None
        for package in available_packages:
            if package.from_code == 'de' and package.to_code == 'en':  # Changed from 'es' to 'de'
                german_to_english_package = package
                break
        
        if german_to_english_package is None:
            raise RuntimeError("German to English package not found")
        
        # Check if already installed
        installed_packages = argostranslate.package.get_installed_packages()
        is_installed = any(pkg.from_code == 'de' and pkg.to_code == 'en'   # Changed from 'es' to 'de'
                          for pkg in installed_packages)
        
        if not is_installed:
            print("Installing German to English translation model...")
            argostranslate.package.install_from_path(
                german_to_english_package.download()
            )
            print("Installation complete!")
        else:
            print("German to English model already installed")
            
    except Exception as e:
        error_logger(e, "Failed to setup translation model")
        raise


def german_to_english(text: str) -> str:  # Changed from spanish_to_english
    """
    Translate German text to English.
    
    Args:
        text (str): German text to translate
        
    Returns:
        str: English translation
        
    Raises:
        RuntimeError: If translation fails
    """
    if not text or not text.strip():
        return text
        
    try:
        return argostranslate.translate.translate(text, 'de', 'en')  # Changed from 'es' to 'de'
    except Exception as e:
        error_logger(e, f"Translation failed for text: {text[:50]}")
        raise RuntimeError(f"Translation failed: {str(e)}")


# Initialize on import
setup_german_to_english()  # Changed from setup_spanish_to_english