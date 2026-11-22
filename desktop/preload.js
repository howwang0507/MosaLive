'use strict';
// The only bridge between the pages and the app. Pages get these functions and nothing else.
const { contextBridge, ipcRenderer } = require('electron');

const listen = channel => callback => {
  const handler = (_event, payload) => callback(payload);
  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
};

contextBridge.exposeInMainWorld('mosa', {
  getState: () => ipcRenderer.invoke('state:get'),
  setSettings: patch => ipcRenderer.invoke('settings:set', patch),
  runChecks: () => ipcRenderer.invoke('checks:run'),
  startService: () => ipcRenderer.invoke('service:start'),
  stopService: () => ipcRenderer.invoke('service:stop'),
  resources: () => ipcRenderer.invoke('service:resources'),
  runSetup: ids => ipcRenderer.invoke('setup:run', ids),
  resetOverlay: () => ipcRenderer.invoke('overlay:reset'),
  openLogs: () => ipcRenderer.invoke('open:logs'),
  sendCaption: caption => ipcRenderer.send('caption', caption),
  setCapturing: on => ipcRenderer.send('capture:state', on),
  lockOverlay: () => ipcRenderer.send('overlay:lock'),
  onStatus: listen('status'), onLog: listen('log'), onChecks: listen('checks'), onSettings: listen('settings'),
  onSetup: listen('setup'), onCommand: listen('command'), onCaption: listen('caption'), onCapture: listen('capture'),
});
