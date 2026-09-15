const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("desktopEnv", {
  platform: process.platform,
  isElectron: true,
});
