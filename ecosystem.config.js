module.exports = {
  apps: [
    {
      name: "skill-factory",
      script: "npm",
      args: "start",
      cwd: __dirname,
      env: {
        NODE_ENV: "production",
        PORT: 3000,
      },
      max_restarts: 10,
      restart_delay: 5000,
      watch: false,
      max_memory_restart: "1G",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      out_file: "./data/logs/app.log",
      error_file: "./data/logs/error.log",
      merge_logs: true,
    },
  ],
};
