"""
Configuration management for flexible alert thresholds and settings
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class StockConfig:
    """Configuration for individual stock tracking"""
    symbol: str
    threshold_percent: float = 1.0  # Default 1% threshold
    max_alerts_per_day: int = 3
    enabled: bool = True
    custom_message_prefix: str = ""
    priority: str = "normal"  # low, normal, high
    last_alert: Optional[str] = None
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass 
class GlobalConfig:
    """Global configuration for the stock tracker"""
    default_threshold_percent: float = 1.0
    max_message_length: int = 160
    rate_limit_per_hour: int = 10
    tracking_enabled: bool = True
    debug_mode: bool = False
    alert_cooldown_hours: int = 24
    research_timeout_seconds: int = 30
    sms_enabled: bool = True
    
    # Market hours (24-hour format)
    market_open_hour: int = 9
    market_close_hour: int = 16
    market_timezone: str = "US/Eastern"
    
    # Alert priorities
    high_priority_threshold: float = 5.0  # 5% or higher gets high priority
    low_priority_threshold: float = 0.5   # Below 0.5% gets low priority
    
    # System limits
    max_tracked_stocks: int = 50
    max_daily_alerts: int = 20


class ConfigManager:
    """Manages configuration for stock tracking and alerts"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.global_config_file = os.path.join(config_dir, "global_config.json")
        self.stocks_config_file = os.path.join(config_dir, "stocks_config.json")
        
        self._ensure_config_dir()
        self.global_config = self._load_global_config()
        self.stocks_config = self._load_stocks_config()
    
    def _ensure_config_dir(self):
        """Ensure configuration directory exists"""
        os.makedirs(self.config_dir, exist_ok=True)
    
    def _load_global_config(self) -> GlobalConfig:
        """Load global configuration"""
        try:
            if os.path.exists(self.global_config_file):
                with open(self.global_config_file, 'r') as f:
                    data = json.load(f)
                return GlobalConfig(**data)
            else:
                # Create default config
                config = GlobalConfig()
                self._save_global_config(config)
                return config
        except Exception as e:
            logger.error(f"Error loading global config: {e}")
            return GlobalConfig()
    
    def _save_global_config(self, config: GlobalConfig) -> bool:
        """Save global configuration"""
        try:
            with open(self.global_config_file, 'w') as f:
                json.dump(asdict(config), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving global config: {e}")
            return False
    
    def _load_stocks_config(self) -> Dict[str, StockConfig]:
        """Load stocks configuration"""
        try:
            if os.path.exists(self.stocks_config_file):
                with open(self.stocks_config_file, 'r') as f:
                    data = json.load(f)
                return {symbol: StockConfig(**config) for symbol, config in data.items()}
            else:
                return {}
        except Exception as e:
            logger.error(f"Error loading stocks config: {e}")
            return {}
    
    def _save_stocks_config(self) -> bool:
        """Save stocks configuration"""
        try:
            data = {symbol: asdict(config) for symbol, config in self.stocks_config.items()}
            with open(self.stocks_config_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving stocks config: {e}")
            return False
    
    def get_stock_config(self, symbol: str) -> StockConfig:
        """Get configuration for a specific stock"""
        symbol = symbol.upper()
        if symbol not in self.stocks_config:
            # Create default config for new stock
            config = StockConfig(
                symbol=symbol,
                threshold_percent=self.global_config.default_threshold_percent
            )
            self.stocks_config[symbol] = config
            self._save_stocks_config()
        return self.stocks_config[symbol]
    
    def update_stock_config(self, symbol: str, **kwargs) -> bool:
        """Update configuration for a specific stock"""
        try:
            symbol = symbol.upper()
            config = self.get_stock_config(symbol)
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    logger.warning(f"Unknown config field: {key}")
            
            self.stocks_config[symbol] = config
            return self._save_stocks_config()
        except Exception as e:
            logger.error(f"Error updating stock config for {symbol}: {e}")
            return False
    
    def remove_stock_config(self, symbol: str) -> bool:
        """Remove configuration for a specific stock"""
        try:
            symbol = symbol.upper()
            if symbol in self.stocks_config:
                del self.stocks_config[symbol]
                return self._save_stocks_config()
            return True
        except Exception as e:
            logger.error(f"Error removing stock config for {symbol}: {e}")
            return False
    
    def get_threshold_for_stock(self, symbol: str) -> float:
        """Get alert threshold for a specific stock"""
        config = self.get_stock_config(symbol)
        return config.threshold_percent
    
    def should_alert(self, symbol: str, price_change_percent: float) -> bool:
        """Check if an alert should be triggered for this stock"""
        config = self.get_stock_config(symbol)
        
        # Check if tracking is enabled
        if not config.enabled or not self.global_config.tracking_enabled:
            return False
        
        # Check threshold
        if abs(price_change_percent) < config.threshold_percent:
            return False
        
        # Check daily alert limit
        today = datetime.now().date().isoformat()
        if config.last_alert == today:
            # Could add more sophisticated daily limit checking here
            return False
        
        return True
    
    def get_priority(self, price_change_percent: float) -> str:
        """Get priority level based on price change"""
        abs_change = abs(price_change_percent)
        
        if abs_change >= self.global_config.high_priority_threshold:
            return "high"
        elif abs_change <= self.global_config.low_priority_threshold:
            return "low"
        else:
            return "normal"
    
    def update_global_config(self, **kwargs) -> bool:
        """Update global configuration"""
        try:
            for key, value in kwargs.items():
                if hasattr(self.global_config, key):
                    setattr(self.global_config, key, value)
                else:
                    logger.warning(f"Unknown global config field: {key}")
            
            return self._save_global_config(self.global_config)
        except Exception as e:
            logger.error(f"Error updating global config: {e}")
            return False
    
    def get_all_configs(self) -> Dict[str, Any]:
        """Get all configurations for display/debugging"""
        return {
            "global": asdict(self.global_config),
            "stocks": {symbol: asdict(config) for symbol, config in self.stocks_config.items()}
        }
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate configuration settings"""
        issues = []
        warnings = []
        
        # Validate global config
        if self.global_config.default_threshold_percent <= 0:
            issues.append("Default threshold must be positive")
        
        if self.global_config.max_tracked_stocks <= 0:
            issues.append("Max tracked stocks must be positive")
        
        if len(self.stocks_config) > self.global_config.max_tracked_stocks:
            warnings.append(f"Tracking {len(self.stocks_config)} stocks, limit is {self.global_config.max_tracked_stocks}")
        
        # Validate stock configs
        for symbol, config in self.stocks_config.items():
            if config.threshold_percent <= 0:
                issues.append(f"{symbol}: threshold must be positive")
            
            if config.threshold_percent > 50:
                warnings.append(f"{symbol}: threshold {config.threshold_percent}% is very high")
            
            if config.max_alerts_per_day <= 0:
                issues.append(f"{symbol}: max alerts per day must be positive")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
    
    def export_config(self, filepath: str) -> bool:
        """Export configuration to a file"""
        try:
            config_data = {
                "global_config": asdict(self.global_config),
                "stocks_config": {symbol: asdict(config) for symbol, config in self.stocks_config.items()},
                "exported_at": datetime.now().isoformat()
            }
            
            with open(filepath, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Configuration exported to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            return False
    
    def import_config(self, filepath: str) -> bool:
        """Import configuration from a file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Import global config
            if "global_config" in data:
                self.global_config = GlobalConfig(**data["global_config"])
                self._save_global_config(self.global_config)
            
            # Import stocks config
            if "stocks_config" in data:
                self.stocks_config = {
                    symbol: StockConfig(**config) 
                    for symbol, config in data["stocks_config"].items()
                }
                self._save_stocks_config()
            
            logger.info(f"Configuration imported from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error importing config: {e}")
            return False


# Global configuration manager instance
config_manager = ConfigManager()


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance"""
    return config_manager


def set_stock_threshold(symbol: str, threshold_percent: float) -> bool:
    """Convenience function to set stock threshold"""
    return config_manager.update_stock_config(symbol, threshold_percent=threshold_percent)


def get_stock_threshold(symbol: str) -> float:
    """Convenience function to get stock threshold"""
    return config_manager.get_threshold_for_stock(symbol)


def should_send_alert(symbol: str, price_change_percent: float) -> bool:
    """Convenience function to check if alert should be sent"""
    return config_manager.should_alert(symbol, price_change_percent)
