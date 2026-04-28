"""
Dollar Bets — Platform Integration Adapters

Each platform (Kalshi, Polymarket, Coinbase, sportsbooks) has its own adapter
that handles fetching, parsing, and normalizing market data.

The canonical market model lives in scanner.py and generate.py.
Adapters are imported by scanner.py when the corresponding platform is enabled.
"""
