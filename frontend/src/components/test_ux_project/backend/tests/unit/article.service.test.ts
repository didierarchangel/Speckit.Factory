// @SPEC-KIT-TASK: 19_tests_backend
import ArticleService from '../../src/services/article.service';
import Article, { IArticle } from '../../src/models/Article';
import { CreateArticleDto, UpdateArticleDto } from '../../src/dtos/article.dto';

// Mock the Article model
jest.mock('../../src/models/Article', () => {
  const mockArticle = {
    find: jest.fn(),
    findById: jest.fn(),
    create: jest.fn(),
    findByIdAndUpdate: jest.fn(),
    findByIdAndDelete: jest.fn(),
  };
  return {
    __esModule: true,
    default: {
      ...mockArticle,
      // Mock static methods or properties if necessary
      schema: {
        path: jest.fn()
      }
    }
  };
});

const mockedArticleModel = Article as jest.Mocked<typeof Article>;

describe('ArticleService Unit Tests', () => {
  beforeEach(() => {
    // Reset all mocks before each test
    jest.clearAllMocks();
  });

  const mockArticleData = {
    _id: '60c72b2f9b1e8b001c8e4d2a',
    title: 'Test Article',
    content: 'This is a test article.',
    author: 'Test Author',
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const mockArticleInstance = {
    ...mockArticleData,
    save: jest.fn().mockResolvedValue(mockArticleData),
    toObject: jest.fn().mockReturnValue(mockArticleData),
  };

  describe('createArticle', () => {
    it('should create a new article', async () => {
      const createDto: CreateArticleDto = {
        body: {
          title: 'New Article',
          content: 'Content of new article',
          author: 'New Author',
        }
      };
      mockedArticleModel.create.mockResolvedValue(mockArticleInstance as any);

      const result = await ArticleService.createArticle(createDto.body);

      expect(mockedArticleModel.create).toHaveBeenCalledWith(createDto.body);
      expect(result).toEqual(mockArticleData);
    });
  });

  describe('findAllArticles', () => {
    it('should return all articles', async () => {
      mockedArticleModel.find.mockResolvedValue([mockArticleInstance] as any);

      const result = await ArticleService.findAllArticles();

      expect(mockedArticleModel.find).toHaveBeenCalledTimes(1);
      expect(result).toEqual([mockArticleData]);
    });
  });

  describe('findArticleById', () => {
    it('should return an article by ID', async () => {
      mockedArticleModel.findById.mockResolvedValue(mockArticleInstance as any);

      const result = await ArticleService.findArticleById(mockArticleData._id);

      expect(mockedArticleModel.findById).toHaveBeenCalledWith(mockArticleData._id);
      expect(result).toEqual(mockArticleData);
    });

    it('should return null if article not found', async () => {
      mockedArticleModel.findById.mockResolvedValue(null);

      const result = await ArticleService.findArticleById('nonexistentId');

      expect(mockedArticleModel.findById).toHaveBeenCalledWith('nonexistentId');
      expect(result).toBeNull();
    });
  });

  describe('updateArticle', () => {
    it('should update an existing article', async () => {
      const updateDto: UpdateArticleDto = {
        body: {
          title: 'Updated Title',
        }
      };
      const updatedArticle = { ...mockArticleData, title: 'Updated Title' };
      const mockUpdatedArticleInstance = {
        ...mockArticleInstance,
        title: 'Updated Title',
        toObject: jest.fn().mockReturnValue(updatedArticle)
      };

      mockedArticleModel.findByIdAndUpdate.mockResolvedValue(mockUpdatedArticleInstance as any);

      const result = await ArticleService.updateArticle(mockArticleData._id, updateDto.body);

      expect(mockedArticleModel.findByIdAndUpdate).toHaveBeenCalledWith(
        mockArticleData._id,
        updateDto.body,
        { new: true }
      );
      expect(result).toEqual(updatedArticle);
    });

    it('should return null if article to update not found', async () => {
      mockedArticleModel.findByIdAndUpdate.mockResolvedValue(null);

      const result = await ArticleService.updateArticle('nonexistentId', { title: 'No Title' });

      expect(mockedArticleModel.findByIdAndUpdate).toHaveBeenCalledWith(
        'nonexistentId',
        { title: 'No Title' },
        { new: true }
      );
      expect(result).toBeNull();
    });
  });

  describe('deleteArticle', () => {
    it('should delete an article by ID', async () => {
      mockedArticleModel.findByIdAndDelete.mockResolvedValue(mockArticleInstance as any);

      const result = await ArticleService.deleteArticle(mockArticleData._id);

      expect(mockedArticleModel.findByIdAndDelete).toHaveBeenCalledWith(mockArticleData._id);
      expect(result).toEqual(mockArticleData);
    });

    it('should return null if article to delete not found', async () => {
      mockedArticleModel.findByIdAndDelete.mockResolvedValue(null);

      const result = await ArticleService.deleteArticle('nonexistentId');

      expect(mockedArticleModel.findByIdAndDelete).toHaveBeenCalledWith('nonexistentId');
      expect(result).toBeNull();
    });
  });
});