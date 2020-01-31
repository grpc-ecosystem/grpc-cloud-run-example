FROM node:12.14

WORKDIR /srv/grpc

COPY server.js *.proto package.json ./

RUN npm install

CMD ["node", "server.js"]