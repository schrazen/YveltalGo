import { contextBridge } from "electron";

contextBridge.exposeInMainWorld("desktopEnv", {
  platform: process.platform,
  isElectron: true,
});
