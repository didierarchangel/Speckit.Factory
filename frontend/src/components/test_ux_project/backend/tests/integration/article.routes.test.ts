// @SPEC-KIT-TASK: 19_tests_backend
import request from 'supertest';
import { app } from '../../src/app';
import mongoose from 'mongoose';
import Article, { IArticle } from '../../src/models/Article';

// Mock mongoose.connect and disconnect to prevent actual database connection during tests
jest.mock('mongoose', () => ({
  ...jest.requireActual('mongoose'),
  connect: jest.fn(() => Promise.resolve()),
  disconnect: jest.fn(() => Promise.resolve()),
  model: jest.fn(jest.requireActual('mongoose').model)
}));

// Mock the Article model itself, which is what the service/controller uses
const mockArticle = {
  find: jest.fn(),
  findById: jest.fn(),
  create: jest.fn(),
  findByIdAndUpdate: jest.fn(),
  findByIdAndDelete: jest.fn(),
};

// Mock the default export of the Article model file
jest.mock('../../src/models/Article', () => ({
  __esModule: true,
  default: {
    ...mockArticle,
    // Add any static methods if they exist on the model
    schema: {
      path: jest.fn()
    }
  },
}));

const mockedArticleModel = Article as jest.Mocked<typeof Article>;

describe('Article Routes Integration Tests', () => {
  // Before running any tests, ensure mongoose connect is called for app initialization
  beforeAll(async () => {
    await (mongoose.connect as jest.Mock).mockResolvedValue(true);
  });

  // After all tests, disconnect mongoose
  afterAll(async () => {
    await (mongoose.disconnect as jest.Mock).mockResolvedValue(true);
  });

  beforeEach(() => {
    jest.clearAllMocks(); // Clear mocks before each test
  });

  const articleId = '60c72b2f9b1e8b001c8e4d2a';
  const mockArticleData = {
    _id: articleId,
    title: 'Test Article',
    content: 'This is a test article content.',
    author: 'Test Author',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  const mockArticleInstance = {
    ...mockArticleData,
    save: jest.fn().mockResolvedValue(mockArticleData),
    toObject: jest.fn().mockReturnValue(mockArticleData),
  };

  describe('GET /api/articles', () => {
    it('should return all articles', async () => {
      mockedArticleModel.find.mockResolvedValue([mockArticleInstance] as any);

      const res = await request(app).get('/api/articles');

      expect(res.statusCode).toEqual(200);
      expect(res.body).toEqual([mockArticleData]);
      expect(mockedArticleModel.find).toHaveBeenCalledTimes(1);
    });

    it('should return an empty array if no articles exist', async () => {
      mockedArticleModel.find.mockResolvedValue([]);

      const res = await request(app).get('/api/articles');

      expect(res.statusCode).toEqual(200);
      expect(res.body).toEqual([]);
    });
  });

  describe('GET /api/articles/:id', () => {
    it('should return an article by ID', async () => {
      mockedArticleModel.findById.mockResolvedValue(mockArticleInstance as any);

      const res = await request(app).get(`/api/articles/${articleId}`);

      expect(res.statusCode).toEqual(200);
      expect(res.body).toEqual(mockArticleData);
      expect(mockedArticleModel.findById).toHaveBeenCalledWith(articleId);
    });

    it('should return 404 if article not found', async () => {
      mockedArticleModel.findById.mockResolvedValue(null);

      const res = await request(app).get(`/api/articles/nonexistentId`);

      expect(res.statusCode).toEqual(404);
      expect(res.body).toEqual({ message: 'Article not found' });
    });

    it('should return 400 for invalid ID format', async () => {
      const res = await request(app).get(`/api/articles/invalid-id-format`);

      expect(res.statusCode).toEqual(400);
      expect(res.body.message).toEqual("Validation error");
      expect(res.body.errors[0].path).toEqual(["params", "id"]);
    });
  });

  describe('POST /api/articles', () => {
    it('should create a new article', async () => {
      const newArticle = {
        title: 'New Article',
        content: 'Content for new article',
        author: 'New Author',
      };
      const createdArticle = { ...mockArticleData, ...newArticle, _id: 'newId' };
      const mockCreatedArticleInstance = {
        ...mockArticleInstance,
        ...newArticle,
        _id: 'newId',
        toObject: jest.fn().mockReturnValue(createdArticle)
      };

      mockedArticleModel.create.mockResolvedValue(mockCreatedArticleInstance as any);

      const res = await request(app)
        .post('/api/articles')
        .send(newArticle);

      expect(res.statusCode).toEqual(201);
      expect(res.body).toEqual(createdArticle);
      expect(mockedArticleModel.create).toHaveBeenCalledWith(newArticle);
    });

    it('should return 400 if validation fails', async () => {
      const invalidArticle = {
        title: '', // Invalid: title is required
        content: 'Content',
        author: 'Author',
      };

      const res = await request(app)
        .post('/api/articles')
        .send(invalidArticle);

      expect(res.statusCode).toEqual(400);
      expect(res.body.message).toEqual('Validation error');
      expect(res.body.errors[0].path).toEqual(["body", "title"]);
    });
  });

  describe('PUT /api/articles/:id', () => {
    it('should update an existing article', async () => {
      const updates = { title: 'Updated Title' };
      const updatedArticle = { ...mockArticleData, ...updates };
      const mockUpdatedArticleInstance = {
        ...mockArticleInstance,
        ...updates,
        toObject: jest.fn().mockReturnValue(updatedArticle)
      };

      mockedArticleModel.findByIdAndUpdate.mockResolvedValue(mockUpdatedArticleInstance as any);

      const res = await request(app)
        .put(`/api/articles/${articleId}`)
        .send(updates);

      expect(res.statusCode).toEqual(200);
      expect(res.body).toEqual(updatedArticle);
      expect(mockedArticleModel.findByIdAndUpdate).toHaveBeenCalledWith(
        articleId,
        updates,
        { new: true }
      );
    });

    it('should return 404 if article to update not found', async () => {
      mockedArticleModel.findByIdAndUpdate.mockResolvedValue(null);

      const res = await request(app)
        .put(`/api/articles/nonexistentId`)
        .send({ title: 'Nonexistent' });

      expect(res.statusCode).toEqual(404);
      expect(res.body).toEqual({ message: 'Article not found' });
    });

    it('should return 400 if validation fails during update', async () => {
      const updates = { title: '' }; // Invalid update

      const res = await request(app)
        .put(`/api/articles/${articleId}`)
        .send(updates);

      expect(res.statusCode).toEqual(400);
      expect(res.body.message).toEqual('Validation error');
      expect(res.body.errors[0].path).toEqual(["body", "title"]);
    });
  });

  describe('DELETE /api/articles/:id', () => {
    it('should delete an article', async () => {
      mockedArticleModel.findByIdAndDelete.mockResolvedValue(mockArticleInstance as any);

      const res = await request(app).delete(`/api/articles/${articleId}`);

      expect(res.statusCode).toEqual(200);
      expect(res.body).toEqual({ message: 'Article deleted successfully' });
      expect(mockedArticleModel.findByIdAndDelete).toHaveBeenCalledWith(articleId);
    });

    it('should return 404 if article to delete not found', async () => {
      mockedArticleModel.findByIdAndDelete.mockResolvedValue(null);

      const res = await request(app).delete(`/api/articles/nonexistentId`);

      expect(res.statusCode).toEqual(404);
      expect(res.body).toEqual({ message: 'Article not found' });
    });
  });
});