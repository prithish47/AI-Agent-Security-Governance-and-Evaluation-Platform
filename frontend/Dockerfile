FROM node:20-alpine

WORKDIR /app

# Copy package files first (Docker layer caching)
COPY package.json package-lock.json* ./
RUN npm install

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Default command (overridden by docker-compose for dev)
CMD ["npm", "run", "dev"]
