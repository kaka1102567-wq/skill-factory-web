export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          API keys, pipeline config, notifications
        </p>
      </div>
      <div className="flex items-center justify-center py-20 border border-dashed border-border rounded-xl">
        <div className="text-center text-muted-foreground">
          <p className="text-4xl mb-3">⚙️</p>
          <p className="text-sm font-medium">Settings Panel</p>
          <p className="text-xs mt-1">API keys, Python path, Telegram notifications</p>
          <p className="text-xs mt-3 text-indigo-400">Coming in Sprint 5</p>
        </div>
      </div>
    </div>
  );
}
