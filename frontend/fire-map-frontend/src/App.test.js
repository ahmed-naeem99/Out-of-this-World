import { render, screen, fireEvent } from '@testing-library/react';
import App from './App';

beforeEach(() => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
  );
});

test('renders FireWatch brand in navbar', () => {
  render(<App />);
  expect(screen.getByText(/FireWatch/i)).toBeInTheDocument();
});

test('renders Sign In button', () => {
  render(<App />);
  expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
});

test('renders layer switch button', () => {
  render(<App />);
  expect(screen.getByTitle(/Switch Data Layer/i)).toBeInTheDocument();
});

test('layer switch button shows Validated Layer by default', () => {
  render(<App />);
  expect(screen.getByTitle(/Switch Data Layer/i)).toHaveTextContent(/Validated Layer/i);
});

test('clicking layer switch toggles to Raw Data Layer', () => {
  render(<App />);
  const btn = screen.getByTitle(/Switch Data Layer/i);
  fireEvent.click(btn);
  expect(btn).toHaveTextContent(/Raw Data Layer/i);
});

test('clicking layer switch again toggles back to Validated Layer', () => {
  render(<App />);
  const btn = screen.getByTitle(/Switch Data Layer/i);
  fireEvent.click(btn);
  fireEvent.click(btn);
  expect(btn).toHaveTextContent(/Validated Layer/i);
});
