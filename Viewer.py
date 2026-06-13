from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from web3 import Web3
import requests
import os
from datetime import datetime

# =========================
# CONFIG
# =========================

RPC_URL = os.getenv(
    "RPC_URL",
    "https://mainnet.infura.io/v3/6110d18324774a17bd41ae0c3d9e382c"
)

STETH_ADDRESS = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"

# =========================
# APP
# =========================

app = FastAPI(title="HODL Viewer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# =========================
# WEB3
# =========================

def get_web3():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        raise Exception("RPC connection failed")

    return w3


ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

# =========================
# STETH BALANCE
# =========================

def get_steth_balance(address: str):
    try:
        w3 = get_web3()

        wallet_address = Web3.to_checksum_address(address)
        steth_contract = Web3.to_checksum_address(STETH_ADDRESS)

        contract = w3.eth.contract(
            address=steth_contract,
            abi=ABI
        )

        raw_balance = contract.functions.balanceOf(
            wallet_address
        ).call()

        return float(w3.from_wei(raw_balance, "ether"))

    except Exception as e:
        raise Exception(f"stETH fetch failed: {str(e)}")

# =========================
# ETH PRICE (USD)
# =========================

def get_eth_usd_price():
    # =========================
    # COINBASE
    # =========================
    try:
        r = requests.get(
            "https://api.coinbase.com/v2/prices/ETH-USD/spot",
            timeout=8
        )

        print("Coinbase status:", r.status_code)
        print("Coinbase raw:", r.text)

        data = r.json()

        if "data" in data and "amount" in data["data"]:
            return float(data["data"]["amount"])

    except Exception as e:
        print("Coinbase error:", str(e))

    # =========================
    # BINANCE
    # =========================
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
            timeout=8
        )

        print("Binance status:", r.status_code)
        print("Binance raw:", r.text)

        data = r.json()

        if "price" in data:
            return float(data["price"])

    except Exception as e:
        print("Binance error:", str(e))

    # =========================
    # COINGECKO
    # =========================
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "ethereum", "vs_currencies": "usd"},
            timeout=10
        )

        print("CoinGecko status:", r.status_code)
        print("CoinGecko raw:", r.text)

        data = r.json()

        return float(data["ethereum"]["usd"])

    except Exception as e:
        print("CoinGecko error:", str(e))

    # =========================
    # FAIL HARD (NOT SILENT)
    # =========================
    raise Exception("ALL PRICE SOURCES FAILED")


# =========================
# GAS ESTIMATE (USD)
# =========================

def estimate_gas_usd(eth_usd: float):
    try:
        w3 = get_web3()

        gas_price = w3.eth.gas_price
        estimated_units = 210000

        total_gas_cost_wei = gas_price * estimated_units

        gas_eth = float(
            w3.from_wei(total_gas_cost_wei, "ether")
        )

        gas_usd = gas_eth * eth_usd

        return gas_usd

    except Exception:
        return 0.0

# =========================
# ROOT
# =========================

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "HODL Viewer API is running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "time": str(datetime.utcnow())
    }

# =========================
# MAIN ENDPOINT
# =========================

@app.get("/wallet/{address}")
def wallet(address: str):

    if not address.startswith("0x") or len(address) != 42:
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum address"
        )

    try:
        steth = get_steth_balance(address)

        eth_usd = get_eth_usd_price()

        value_usd = steth * eth_usd

        gas_usd = estimate_gas_usd(eth_usd)

        return {
            "address": address,
            "steth_balance": round(steth, 6),
            "value_usd": round(value_usd, 2),
            "gas_usd": round(gas_usd, 2),
            "updated_at": str(datetime.utcnow())
        }

    except Exception as e:
        return {
            "error": str(e),
            "status": "failed",
            "updated_at": str(datetime.utcnow())
        }