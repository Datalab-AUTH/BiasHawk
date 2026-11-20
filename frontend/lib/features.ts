/**
 * Switches for things that are built but deliberately not offered yet.
 *
 * Kept in one file so turning one back on is a one-line change rather than a
 * hunt through the pages that reference it.
 */

/**
 * Self-service account creation.
 *
 * Off for now: accounts are made by hand. The sign-up page redirects to
 * sign-in and the invitation to create one is hidden while this is false.
 * Note the API's signup endpoint stays open, so this is a product decision
 * rather than a security boundary.
 */
export const SIGN_UP_ENABLED = false;
