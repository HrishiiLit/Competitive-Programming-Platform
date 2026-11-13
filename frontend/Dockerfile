FROM node:18-alpine

WORKDIR /app

ENV NODE_ENV=development

COPY package.json* package-lock.json* ./
RUN if [ -f package.json ]; then npm install; fi

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]
