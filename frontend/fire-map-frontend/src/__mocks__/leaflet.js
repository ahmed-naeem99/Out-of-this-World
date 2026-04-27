const L = {
  Icon: {
    Default: {
      prototype: {},
      mergeOptions: jest.fn(),
    },
  },
  divIcon: jest.fn(() => ({ options: {} })),
  canvas: jest.fn(() => ({})),
};

module.exports = L;
