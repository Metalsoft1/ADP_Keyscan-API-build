import pandas as pd

path = "samples/dataset.xlsx"
raw = pd.read_excel(path, header=None).fillna("")

required = {"Credential_Number", "DateTime", "Location"}
hdr = None

for i in range(min(len(raw), 500)):
    vals = set(raw.iloc[i].astype(str).str.strip().tolist())
    # exact token match rather than substring-in-a-long-query
    if required.issubset(vals):
        hdr = i
        break

print("Detected header row:", hdr)
if hdr is not None:
    print("Header tokens found:", [v for v in raw.iloc[hdr].astype(str).str.strip().tolist() if v])
