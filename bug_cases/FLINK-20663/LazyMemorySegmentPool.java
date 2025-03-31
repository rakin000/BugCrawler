/** {@link MemorySegmentPool} that lazy allocate memory pages from {@link MemoryManager}. */
public class LazyMemorySegmentPool implements MemorySegmentPool, Closeable {

    private static final long PER_REQUEST_MEMORY_SIZE = 16 * 1024 * 1024;

    private final Object owner;
    private final MemoryManager memoryManager;
    private final ArrayList<MemorySegment> cachePages;
    private final int maxPages;
    private final int perRequestPages;

    private int pageUsage;

    public LazyMemorySegmentPool(Object owner, MemoryManager memoryManager, int maxPages) {
        this.owner = owner;
        this.memoryManager = memoryManager;
        this.cachePages = new ArrayList<>();
        this.maxPages = maxPages;
        this.pageUsage = 0;
        this.perRequestPages =
                Math.max(1, (int) (PER_REQUEST_MEMORY_SIZE / memoryManager.getPageSize()));
    }

    @Override
    public int pageSize() {
        return this.memoryManager.getPageSize();
    }

    @Override
    public void returnAll(List<MemorySegment> memory) {
        this.pageUsage -= memory.size();
        if (this.pageUsage < 0) {
            throw new RuntimeException("Return too more memories.");
        }
        this.cachePages.addAll(memory);
    }

    public void returnPage(MemorySegment segment) {
        returnAll(Collections.singletonList(segment));
    }

    @Override
    public MemorySegment nextSegment() {
        int freePages = freePages();
        if (freePages == 0) {
            return null;
        }

        if (this.cachePages.isEmpty()) {
            int numPages = Math.min(freePages, this.perRequestPages);
            try {
                this.memoryManager.allocatePages(owner, this.cachePages, numPages);
            } catch (MemoryAllocationException e) {
                throw new RuntimeException(e);
            }
        }
        this.pageUsage++;
        return this.cachePages.remove(this.cachePages.size() - 1);
    }

    public List<MemorySegment> allocateSegments(int required) {
        int freePages = freePages();
        if (freePages < required) {
            return null;
        }

        List<MemorySegment> ret = new ArrayList<>(required);
        for (int i = 0; i < required; i++) {
            MemorySegment segment;
            try {
                segment = nextSegment();
                Preconditions.checkNotNull(segment);
            } catch (Throwable t) {
                // unexpected, we should first return all temporary segments
                returnAll(ret);
                throw t;
            }
            ret.add(segment);
        }
        return ret;
    }

    @Override
    public int freePages() {
        return this.maxPages - this.pageUsage;
    }

    @Override
    public void close() {
        if (this.pageUsage != 0) {
            throw new RuntimeException(
                    "Should return all used memory before clean, page used: " + pageUsage);
        }
        cleanCache();
    }

    public void cleanCache() {
        this.memoryManager.release(this.cachePages);
    }
}