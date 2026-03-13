// @SPEC-KIT-TASK: 19_tests_backend
import request from 'supertest';
import app from '../../src/app';

describe('Integration Test: Health Check', () => {
  it('should return 200 and a success message for /api/health', async () => {
    const res = await request(app).get('/api/health');
    expect(res.statusCode).toEqual(200);
    expect(res.body).toEqual({ status: 'UP', message: 'Backend is healthy!' });
  });
});