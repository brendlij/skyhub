import { createRouter, createWebHistory } from "vue-router";
import MonitorView from "./views/MonitorView.vue";
import CaptureExplorerView from "./views/CaptureExplorerView.vue";
import SettingsView from "./views/SettingsView.vue";
import NodesView from "./views/NodesView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/monitor" },
    { path: "/monitor", component: MonitorView },
    { path: "/captures", component: CaptureExplorerView },
    { path: "/settings", component: SettingsView },
    { path: "/nodes", component: NodesView }
  ]
});
