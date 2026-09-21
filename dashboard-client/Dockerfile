# Module 14 — image du dashboard client (build React puis service statique)
# Contexte de build = dashboard-client/ (autonome : ne parle à l'API
# qu'en HTTP depuis le navigateur, pas de dépendance fichier aux autres
# modules).

# --- Étape 1 : build de l'application Vite/React ---------------------
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- Étape 2 : servir les fichiers statiques avec nginx ---------------
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
