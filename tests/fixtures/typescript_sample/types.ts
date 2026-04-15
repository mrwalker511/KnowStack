/** Core domain types for the TypeScript sample. */

export interface User {
    id: number;
    email: string;
    hashedPassword: string;
}

export interface Token {
    value: string;
    userId: number;
}

export type AuthResult = {
    token: Token;
    user: User;
};
