import os
import requests
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

# -----------------------------
# CONFIG
# -----------------------------

CTF_ADDRESS = Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACe5EA0476045")
USDCe_ADDRESS = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")

CTF_ABI = [{
  "inputs":[
    {"internalType":"address","name":"collateralToken","type":"address"},
    {"internalType":"bytes32","name":"parentCollectionId","type":"bytes32"},
    {"internalType":"bytes32","name":"conditionId","type":"bytes32"},
    {"internalType":"uint256[]","name":"indexSets","type":"uint256[]"}
  ],
  "name":"redeemPositions",
  "outputs":[],
  "stateMutability":"nonpayable",
  "type":"function"
}]

# -----------------------------
# HELPERS
# -----------------------------

def get_closed_markets_with_condition(gamma_host, series_slug):
    url = f"{gamma_host}/markets"
    params = {
        "limit": 200,
        "closed": "true",
        "archived": "false"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    markets = r.json()

    out = []
    for m in markets:
        slug = str(m.get("slug", ""))
        if slug.startswith("btc-updown-5m-"):
            if m.get("conditionId"):
                out.append(m)
    return out

# -----------------------------
# REDEEM
# -----------------------------

def redeem_condition(w3, private_key, condition_id_hex):
    acct = Account.from_key(private_key)
    from_addr = acct.address

    ctf = w3.eth.contract(address=CTF_ADDRESS, abi=CTF_ABI)

    condition_id = bytes.fromhex(condition_id_hex.replace("0x",""))

    tx = ctf.functions.redeemPositions(
        USDCe_ADDRESS,
        b"\x00" * 32,
        condition_id,
        [1,2]  # YES/NO
    ).build_transaction({
        "from": from_addr,
        "nonce": w3.eth.get_transaction_count(from_addr),
        "chainId": 137,
    })

    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)
    tx["maxFeePerGas"] = w3.eth.gas_price
    tx["maxPriorityFeePerGas"] = 0

    signed = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(signed.rawTransaction)
    return txh.hex()

# -----------------------------
# MAIN
# -----------------------------

def main():
    load_dotenv()

    gamma_host = os.getenv("GAMMA_HOST", "https://gamma-api.polymarket.com")
    private_key = os.getenv("PRIVATE_KEY")
    rpc = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")

    if not private_key:
        raise RuntimeError("PRIVATE_KEY no definida")

    w3 = Web3(Web3.HTTPProvider(rpc))
    if not w3.is_connected():
        raise RuntimeError("No conecta a Polygon RPC")

    print("Buscando markets cerrados...")

    markets = get_closed_markets_with_condition(gamma_host, "btc-up-or-down-5m")

    if not markets:
        print("No hay markets cerrados con conditionId.")
        return

    for m in markets:
        slug = m["slug"]
        condition_id = m["conditionId"]

        print(f"Intentando redeem: {slug}")
        try:
            tx = redeem_condition(w3, private_key, condition_id)
            print(f"Redeem enviado TX: {tx}")
        except Exception as e:
            print(f"Error en {slug}: {e}")

if __name__ == "__main__":
    main()
