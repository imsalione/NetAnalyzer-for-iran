#!/usr/bin/env python3
"""
Internet Monitor v3.0 - Clean Rewrite
Minimal and non-intrusive internet monitoring
"""

import sys
from PyQt6.QtWidgets import QApplication

from monitor.ui.tray_app import TrayApplication
from monitor.utils.logger import setup_logger


def main():
    """Main entry point."""
    logger = setup_logger()
    logger.info("=" * 50)
    logger.info("Internet Monitor v3.0 - Starting")
    logger.info("=" * 50)
    
    try:
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("Internet Monitor")
        app.setOrganizationName("InternetMonitor")
        app.setApplicationVersion("3.0.0")
        app.setQuitOnLastWindowClosed(False)
        
        # Setup async loop
        import qasync
        import asyncio
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # Create tray application
        tray_app = TrayApplication()
        
        logger.info("Application running")
        
        with loop:
            return loop.run_forever()
            
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1
    finally:
        logger.info("Application shutdown")


if __name__ == "__main__":
    sys.exit(main())
