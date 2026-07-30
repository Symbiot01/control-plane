def _clean_pem_string(s: str) -> bytes:
    if "\\n" in s:
        s = s.replace("\\n", "\n")
    start = s.find("-----BEGIN")
    end = s.rfind("-----")
    if start != -1 and end != -1:
        s = s[start:end+5]
    return s.encode("utf-8")

s = '\"-----BEGIN PRIVATE KEY-----\\nMIIEvg...-----END PRIVATE KEY-----\\n\"'
cleaned = _clean_pem_string(s)
print(cleaned)
