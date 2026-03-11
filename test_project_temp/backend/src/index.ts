/**
 * @SPEC-KIT-TASK: Server entrypoint
 * Starts the Express backend server
 */

import app from './app';

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`🚀 Server running at http://localhost:${PORT}`);
});
