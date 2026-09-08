# 1. Python ka base system (Linux)
FROM python:3.10-slim

# 2. Ye line Railway ko force karegi ki AI ke liye libgomp1 install kare
RUN apt-get update && apt-get install -y libgomp1

# 3. Server ke andar folder banana
WORKDIR /app

# 4. Requirements install karna
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Aapka saara code server me copy karna
COPY . .

# 6. API Server start karna (Railway ke PORT ke sath)
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port $PORT"
