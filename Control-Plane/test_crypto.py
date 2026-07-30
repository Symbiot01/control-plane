import re
from cryptography.hazmat.primitives.serialization import load_pem_private_key

def _clean_pem_string(s: str, is_private: bool = True) -> bytes:
    header_match = re.search(r'-----BEGIN.*?-----', s)
    footer_match = re.search(r'-----END.*?-----', s)
    
    if not header_match or not footer_match:
        raise ValueError("Missing headers")
        
    header = header_match.group(0)
    footer = footer_match.group(0)
    
    payload = s[header_match.end():footer_match.start()]
    
    payload = payload.replace("\\n", "")
    payload = payload.replace("\\r", "")
    
    clean_payload = re.sub(r'[^A-Za-z0-9+/=]', '', payload)
    
    lines = [clean_payload[i:i+64] for i in range(0, len(clean_payload), 64)]
    payload_formatted = "\n".join(lines)
    
    perfect_pem = f"{header}\n{payload_formatted}\n{footer}"
    return perfect_pem.encode("utf-8")

with open('.env', 'r') as f:
    env_content = f.read()

match = re.search(r'JWT_PRIVATE_KEY="(.*?)"', env_content, re.DOTALL)
if match:
    s = match.group(1)
    # Inject insane garbage
    s = s.replace('\n', '\\\\\\n') # backslash backslash backslash n
    
    cleaned = _clean_pem_string(s)
    try:
        load_pem_private_key(cleaned, password=None)
        print("Success loading private key!")
    except Exception as e:
        print(f"Error: {e}")
