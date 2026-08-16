// @ts-check
import { defineConfig } from '@vivliostyle/cli';

export default defineConfig({
  title: "Duas for Salah and Supplication",
  author: "Ahmmad Ismail",
  language: "en",
  browser: "chrome@150.0.7871.115",
  image: "ghcr.io/vivliostyle/cli:11.1.0",
  entry: ["duas.html"],
  toc: {
    title: 'Table of Contents',
  },
});
